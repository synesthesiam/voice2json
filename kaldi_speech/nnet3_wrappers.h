// nnet3_wrappers.h
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

#include <base/kaldi-common.h>
#include <util/common-utils.h>
#include <fstext/fstext-lib.h>
#include <nnet3/nnet-am-decodable-simple.h>
#include <online2/online-nnet3-decoding.h>
#include <online2/online-nnet2-feature-pipeline.h>
#include <decoder/lattice-faster-decoder.h>
#include <decoder/lattice-faster-decoder.h>
#include <nnet3/decodable-simple-looped.h>

namespace kaldi {
    class NNet3OnlineModelWrapper {
    friend class NNet3OnlineDecoderWrapper;
    public:
  
        NNet3OnlineModelWrapper(BaseFloat    beam,
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
                                std::string &align_lex_filename
                               ) ;
        ~NNet3OnlineModelWrapper();

    private:

        fst::SymbolTable                          *word_syms;

        // feature_config includes configuration for the iVector adaptation,
        // as well as the basic features.
        OnlineNnet2FeaturePipelineConfig           feature_config;
        LatticeFasterDecoderConfig                 lattice_faster_decoder_config;   
        
        OnlineNnet2FeaturePipelineInfo            *feature_info;

        nnet3::AmNnetSimple                        am_nnet;
        nnet3::NnetSimpleLoopedComputationOptions  decodable_opts;

        TransitionModel                            trans_model;
        //fst::VectorFst<fst::StdArc>               *decode_fst;
        fst::Fst<fst::StdArc>                     *decode_fst;
        std::string                               *ie_conf_filename;

        // word alignment:
        std::vector<std::vector<int32> >           word_alignment_lexicon;
    };

    class NNet3OnlineDecoderWrapper {
    public:
  
        NNet3OnlineDecoderWrapper(NNet3OnlineModelWrapper *aModel);
        ~NNet3OnlineDecoderWrapper();

        bool               decode(BaseFloat  samp_freq, 
                                  int32      num_frames, 
                                  BaseFloat *frames, 
                                  bool       finalize);

        void               get_decoded_string(std::string &decoded_string, 
                                              double &likelihood);
        bool               get_word_alignment(std::vector<string> &words,
                                              std::vector<int32>  &times,
                                              std::vector<int32>  &lengths);

    private:

        void start_decoding(void);
        void free_decoder(void);

        NNet3OnlineModelWrapper                   *model;

        OnlineIvectorExtractorAdaptationState     *adaptation_state;
        OnlineNnet2FeaturePipeline                *feature_pipeline;
        OnlineSilenceWeighting                    *silence_weighting;
        nnet3::DecodableNnetSimpleLoopedInfo      *decodable_info;
        SingleUtteranceNnet3Decoder               *decoder;

        std::vector<std::pair<int32, BaseFloat> >  delta_weights;
        int32                                      tot_frames, tot_frames_decoded;

        // decoding result:
        CompactLattice                             best_path_clat;

    };



}

