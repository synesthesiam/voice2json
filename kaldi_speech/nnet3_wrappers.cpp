// nnet3_wrappers.cpp
//
// Copyright 2016, 2017 G. Bartsch
//
// based on Kaldi's decoder/decoder-wrappers.cc

// Copyright 2014  Johns Hopkins University (author: Daniel Povey)

// See ../../COPYING for clarification regarding multiple authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//  http://www.apache.org/licenses/LICENSE-2.0
//
// THIS CODE IS PROVIDED *AS IS* BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, EITHER EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION ANY IMPLIED
// WARRANTIES OR CONDITIONS OF TITLE, FITNESS FOR A PARTICULAR PURPOSE,
// MERCHANTABLITY OR NON-INFRINGEMENT.
// See the Apache 2 License for the specific language governing permissions and
// limitations under the License.
//

#include "nnet3_wrappers.h"

#include "lat/lattice-functions.h"
#include "lat/word-align-lattice-lexicon.h"
#include "nnet3/nnet-utils.h"

#define VERBOSE 0

namespace kaldi {

    /*
     * NNet3OnlineDecoderWrapper
     */

    NNet3OnlineDecoderWrapper::NNet3OnlineDecoderWrapper(NNet3OnlineModelWrapper *aModel) : model(aModel) {
        decoder            = NULL;
        silence_weighting  = NULL;
        feature_pipeline   = NULL;
        adaptation_state   = NULL;
        decodable_info     = NULL;

        tot_frames         = 0;
        tot_frames_decoded = 0;

#if VERBOSE
        KALDI_LOG << "alloc: OnlineIvectorExtractorAdaptationState";
#endif
        adaptation_state  = new OnlineIvectorExtractorAdaptationState (model->feature_info->ivector_extractor_info);

#if VERBOSE
        KALDI_LOG << "alloc: OnlineSilenceWeighting";
#endif
        silence_weighting = new OnlineSilenceWeighting (model->trans_model, 
                                                        model->feature_info->silence_weighting_config,
                                                        model->decodable_opts.frame_subsampling_factor);
        
#if VERBOSE
        KALDI_LOG << "alloc: nnet3::DecodableNnetSimpleLoopedInfo";
#endif
        decodable_info = new nnet3::DecodableNnetSimpleLoopedInfo(model->decodable_opts, &model->am_nnet);
    }

    NNet3OnlineDecoderWrapper::~NNet3OnlineDecoderWrapper() {
        free_decoder();
        if (silence_weighting) {
            delete silence_weighting ;
            silence_weighting = NULL;
        }
        if (adaptation_state) {
            delete adaptation_state ;
            adaptation_state = NULL;
        }
        if (decodable_info) {
            delete decodable_info;
            decodable_info = NULL;
        }
    }

    void NNet3OnlineDecoderWrapper::start_decoding(void) {
#if VERBOSE
        KALDI_LOG << "start_decoding..." ;
        KALDI_LOG << "max_active  :" << model->lattice_faster_decoder_config.max_active;
        KALDI_LOG << "min_active  :" << model->lattice_faster_decoder_config.min_active;
        KALDI_LOG << "beam        :" << model->lattice_faster_decoder_config.beam;
        KALDI_LOG << "lattice_beam:" << model->lattice_faster_decoder_config.lattice_beam;
#endif
        free_decoder();
#if VERBOSE
        KALDI_LOG << "alloc: OnlineNnet2FeaturePipeline";
#endif
        feature_pipeline  = new OnlineNnet2FeaturePipeline (*model->feature_info);
        feature_pipeline->SetAdaptationState(*adaptation_state);
#if VERBOSE
        KALDI_LOG << "alloc: SingleUtteranceNnet3Decoder";
#endif
        decoder           = new SingleUtteranceNnet3Decoder (model->lattice_faster_decoder_config,
                                                             model->trans_model,
                                                             *decodable_info,
                                                             *model->decode_fst,
                                                             feature_pipeline);
#if VERBOSE
        KALDI_LOG << "start_decoding...done" ;
#endif
    }

    void NNet3OnlineDecoderWrapper::free_decoder(void) {
        if (decoder) {
#if VERBOSE
            KALDI_LOG << "free_decoder";
#endif
            delete decoder ;
            decoder = NULL;
        }
        if (feature_pipeline) {
            delete feature_pipeline ; 
            feature_pipeline = NULL;
        }
    }

    void NNet3OnlineDecoderWrapper::get_decoded_string(std::string &decoded_string, double &likelihood) {

        //std::string                                decoded_string;
        //double                                     likelihood;

        Lattice best_path_lat;

        decoded_string = "";

        if (decoder) {

            // decoding is not finished yet, so we will look up the best partial result so far

            if (decoder->NumFramesDecoded() == 0) {
                likelihood = 0.0;
                return;
            }

            decoder->GetBestPath(false, &best_path_lat);

        } else {
            ConvertLattice(best_path_clat, &best_path_lat);
        }
            
        std::vector<int32> words;
        std::vector<int32> alignment;
        LatticeWeight      weight;
        int32              num_frames;
        GetLinearSymbolSequence(best_path_lat, &alignment, &words, &weight);
        num_frames = alignment.size();
        likelihood = -(weight.Value1() + weight.Value2()) / num_frames;
                   
        for (size_t i = 0; i < words.size(); i++) {
            std::string s = model->word_syms->Find(words[i]);
            if (s == "")
                KALDI_ERR << "Word-id " << words[i] << " not in symbol table.";
            decoded_string += s + ' ';
        }
    }

    bool NNet3OnlineDecoderWrapper::get_word_alignment(std::vector<string> &words,
                                                std::vector<int32>  &times,
                                                std::vector<int32>  &lengths) {

        WordAlignLatticeLexiconInfo lexicon_info(model->word_alignment_lexicon);

#if VERBOSE
        KALDI_LOG << "word alignment starts...";
#endif
        CompactLattice aligned_clat;
        WordAlignLatticeLexiconOpts opts;

        bool ok = WordAlignLatticeLexicon(best_path_clat, model->trans_model, lexicon_info, opts, &aligned_clat);

        if (!ok) {
            KALDI_WARN << "Lattice did not align correctly";
            return false;
        } else {
            if (aligned_clat.Start() == fst::kNoStateId) {
                KALDI_WARN << "Lattice was empty";
                return false;
            } else {
#if VERBOSE
                KALDI_LOG << "Aligned lattice.";
#endif
                TopSortCompactLatticeIfNeeded(&aligned_clat);

                // lattice-1best

                CompactLattice best_path_aligned;
                CompactLatticeShortestPath(aligned_clat, &best_path_aligned); 

                // nbest-to-ctm

                std::vector<int32> word_idxs;
                if (!CompactLatticeToWordAlignment(best_path_aligned, &word_idxs, &times, &lengths)) {
                    KALDI_WARN << "CompactLatticeToWordAlignment failed.";
                    return false;
                }

                // lexicon lookup
                words.clear();
                for (size_t i = 0; i < word_idxs.size(); i++) {
                    std::string s = model->word_syms->Find(word_idxs[i]);
                    if (s == "") {
                        KALDI_ERR << "Word-id " << word_idxs[i] << " not in symbol table.";
                    }
                    words.push_back(s);
                }
            }
        }
        return true;
    }



    bool NNet3OnlineDecoderWrapper::decode(BaseFloat samp_freq, int32 num_frames, BaseFloat *frames, bool finalize) {

        using fst::VectorFst;

        if (!decoder) {
            start_decoding();
        }

        Vector<BaseFloat> wave_part(num_frames, kUndefined);
        for (int i=0; i<num_frames; i++) {
            wave_part(i) = frames[i];
        }
        tot_frames += num_frames;

#if VERBOSE
        KALDI_LOG << "AcceptWaveform...";
#endif
        feature_pipeline->AcceptWaveform(samp_freq, wave_part);

        if (finalize) {
            // no more input. flush out last frames
            feature_pipeline->InputFinished();
        }

        if (silence_weighting->Active() && feature_pipeline->IvectorFeature() != NULL) {
            silence_weighting->ComputeCurrentTraceback(decoder->Decoder());
            silence_weighting->GetDeltaWeights(feature_pipeline->NumFramesReady(),
                                               &delta_weights);
            feature_pipeline->IvectorFeature()->UpdateFrameWeights(delta_weights);
        }

        decoder->AdvanceDecoding();

        if (finalize) {
            decoder->FinalizeDecoding();

            CompactLattice clat;
            bool end_of_utterance = true;
            decoder->GetLattice(end_of_utterance, &clat);

            if (clat.NumStates() == 0) {
              KALDI_WARN << "Empty lattice.";
              return false;
            }

            CompactLatticeShortestPath(clat, &best_path_clat);
            
            tot_frames_decoded = tot_frames;
            tot_frames         = 0;

            free_decoder();

        }
        
        return true;
    }


    /*
     * NNet3OnlineModelWrapper
     */

    // typedef void (*LogHandler)(const LogMessageEnvelope &envelope,
    //                            const char *message);
    void silent_log_handler (const LogMessageEnvelope &envelope,
                             const char *message) {
        // nothing - this handler simply keeps silent
    }

    NNet3OnlineModelWrapper::NNet3OnlineModelWrapper(BaseFloat    beam,                       
                                                     int32        max_active,
                                                     int32        min_active,
                                                     BaseFloat    lattice_beam,
                                                     BaseFloat    acoustic_scale, 
                                                     int32        frame_subsampling_factor,
                                                     std::string &word_syms_filename, 
                                                     std::string &model_in_filename,
                                                     std::string &fst_in_str,
                                                     std::string &mfcc_config,
                                                     std::string &ie_conf_filename,
                                                     std::string &align_lex_filename)

    {

        using namespace kaldi;
        using namespace fst;
        
        typedef kaldi::int32 int32;
        typedef kaldi::int64 int64;
    
#if VERBOSE
        KALDI_LOG << "model_in_filename:         " << model_in_filename;
        KALDI_LOG << "fst_in_str:                " << fst_in_str;
        KALDI_LOG << "mfcc_config:               " << mfcc_config;
        KALDI_LOG << "ie_conf_filename:          " << ie_conf_filename;
        KALDI_LOG << "align_lex_filename:        " << align_lex_filename;
#else
        // silence kaldi output as well
        SetLogHandler(silent_log_handler);
#endif

        feature_config.mfcc_config                 = mfcc_config;
        feature_config.ivector_extraction_config   = ie_conf_filename;

        lattice_faster_decoder_config.max_active   = max_active;
        lattice_faster_decoder_config.min_active   = min_active;
        lattice_faster_decoder_config.beam         = beam;
        lattice_faster_decoder_config.lattice_beam = lattice_beam;
        decodable_opts.acoustic_scale              = acoustic_scale;
        decodable_opts.frame_subsampling_factor    = frame_subsampling_factor;

        feature_info = new OnlineNnet2FeaturePipelineInfo(this->feature_config);

        // load model...
        {
            bool binary;
            Input ki(model_in_filename, &binary);
            this->trans_model.Read(ki.Stream(), binary);
            this->am_nnet.Read(ki.Stream(), binary);
            SetBatchnormTestMode(true, &(this->am_nnet.GetNnet()));
            SetDropoutTestMode(true, &(this->am_nnet.GetNnet()));
            nnet3::CollapseModel(nnet3::CollapseModelConfig(), &(this->am_nnet.GetNnet()));
        }

        // Input FST is just one FST, not a table of FSTs.
        decode_fst = fst::ReadFstKaldiGeneric(fst_in_str);

        word_syms = NULL;
        if (word_syms_filename != "") 
          if (!(word_syms = fst::SymbolTable::ReadText(word_syms_filename)))
            KALDI_ERR << "Could not read symbol table from file "
                       << word_syms_filename;

#if VERBOSE
        KALDI_LOG << "loading word alignment lexicon...";
#endif
        {
            bool binary_in;
            Input ki(align_lex_filename, &binary_in);
            KALDI_ASSERT(!binary_in && "Not expecting binary file for lexicon");
            if (!ReadLexiconForWordAlign(ki.Stream(), &word_alignment_lexicon)) {
                KALDI_ERR << "Error reading alignment lexicon from "
                          << align_lex_filename;
            }
        }
    }

    NNet3OnlineModelWrapper::~NNet3OnlineModelWrapper() {
        delete feature_info;
    }

}

