# distutils: language = c++
# distutils: sources = nnet3.cpp
# cython: language_level = 3

#
# Copyright 2016, 2017, 2018 G. Bartsch
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# THIS CODE IS PROVIDED *AS IS* BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, EITHER EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION ANY IMPLIED
# WARRANTIES OR CONDITIONS OF TITLE, FITNESS FOR A PARTICULAR PURPOSE,
# MERCHANTABLITY OR NON-INFRINGEMENT.
# See the Apache 2 License for the specific language governing permissions and
# limitations under the License.
#

import cython
from libcpp.string cimport string
from libcpp.vector cimport vector
import numpy as np
cimport numpy as cnp
import struct
import wave
import os
from tempfile import NamedTemporaryFile

cdef extern from "nnet3_wrappers.h" namespace "kaldi":

    cdef cppclass NNet3OnlineModelWrapper:
        NNet3OnlineModelWrapper() except +
        NNet3OnlineModelWrapper(float, int, int, float, float, int, string, string, string, string, string, string) except +

    cdef cppclass NNet3OnlineDecoderWrapper:
        NNet3OnlineDecoderWrapper() except +
        NNet3OnlineDecoderWrapper(NNet3OnlineModelWrapper *) except +

        bint decode(float, int, float *, bint) except +

        void get_decoded_string(string &, float &) except +
        bint get_word_alignment(vector[string] &, vector[int] &, vector[int] &) except +

cdef class KaldiNNet3OnlineModel:

    cdef NNet3OnlineModelWrapper* model_wrapper
    cdef str                      modeldir, graphdir
    cdef object                   ie_conf_f

    def __cinit__(self, object modeldir,
                        object graphdir                 = None,
                        float  beam                     = 15.0,
                        int    max_active               = 7000,
                        int    min_active               = 200,
                        float  lattice_beam             = 8.0,
                        float  acoustic_scale           = 1.0, # nnet3: 0.1
                        int    frame_subsampling_factor = 3,   # neet3: 1

                        int    num_gselect              = 5,
                        float  min_post                 = 0.025,
                        float  posterior_scale          = 0.1,
                        int    max_count                = 0,
                        int    online_ivector_period    = 10):

        self.modeldir         = str(modeldir)
        if graphdir is None:
            self.graphdir     = "%s/graph" % self.model_dir
        else:
            self.graphdir     = str(graphdir)

        cdef str mfcc_config           = "%s/conf/mfcc_hires.conf"                  % self.modeldir
        cdef str word_symbol_table     = "%s/words.txt"                             % self.graphdir
        cdef str model_in_filename     = "%s/model/final.mdl"                       % self.modeldir
        cdef str splice_conf_filename  = "%s/ivectors_test_hires/conf/splice.conf"  % self.modeldir
        cdef str fst_in_str            = "%s/HCLG.fst"                           % self.graphdir
        cdef str align_lex_filename    = "%s/phones/align_lexicon.int"           % self.graphdir

        #
        # make sure all model files required exist
        #

        for conff in [mfcc_config, word_symbol_table, model_in_filename, splice_conf_filename, fst_in_str, align_lex_filename]:
            if not os.path.isfile(conff):
                raise Exception ("%s not found." % conff)
            if not os.access(conff, os.R_OK):
                raise Exception ("%s is not readable" % conff)

        #
        # generate ivector_extractor.conf
        #

        self.ie_conf_f = NamedTemporaryFile(prefix="ivector_extractor_", suffix=".conf", mode="w", delete=True)

        print("--cmvn-config=%s/conf/online_cmvn.conf" % self.modeldir, file=self.ie_conf_f)
        print("--ivector-period=%d" % online_ivector_period, file=self.ie_conf_f)
        print("--splice-config=%s" % splice_conf_filename, file=self.ie_conf_f)
        print("--lda-matrix=%s/extractor/final.mat" % self.modeldir, file=self.ie_conf_f)
        print("--global-cmvn-stats=%s/extractor/global_cmvn.stats" % self.modeldir, file=self.ie_conf_f)
        print("--diag-ubm=%s/extractor/final.dubm" % self.modeldir, file=self.ie_conf_f)
        print("--ivector-extractor=%s/extractor/final.ie" % self.modeldir, file=self.ie_conf_f)
        print("--num-gselect=%d" % num_gselect, file=self.ie_conf_f)
        print("--min-post=%f" % min_post, file=self.ie_conf_f)
        print("--posterior-scale=%f" % posterior_scale, file=self.ie_conf_f)
        print("--max-remembered-frames=1000", file=self.ie_conf_f)
        print("--max-count=%d" % max_count, file=self.ie_conf_f)
        self.ie_conf_f.flush()

        #
        # instantiate our C++ wrapper class
        #

        self.model_wrapper = new NNet3OnlineModelWrapper(beam,
                                                         max_active,
                                                         min_active,
                                                         lattice_beam,
                                                         acoustic_scale,
                                                         frame_subsampling_factor,
                                                         word_symbol_table.encode(),
                                                         model_in_filename.encode(),
                                                         fst_in_str.encode(),
                                                         mfcc_config.encode(),
                                                         self.ie_conf_f.name.encode(),
                                                         align_lex_filename.encode())

    def __dealloc__(self):
        if self.ie_conf_f:
            self.ie_conf_f.close()
        if self.model_wrapper:
            del self.model_wrapper

cdef class KaldiNNet3OnlineDecoder:

    cdef NNet3OnlineDecoderWrapper* decoder_wrapper
    cdef object                     ie_conf_f

    def __cinit__(self, KaldiNNet3OnlineModel model):

        #
        # instantiate our C++ wrapper class
        #

        self.decoder_wrapper = new NNet3OnlineDecoderWrapper(model.model_wrapper)

    def __dealloc__(self):
        del self.decoder_wrapper

    def decode(self, samp_freq, cnp.ndarray[float, ndim=1, mode="c"] samples not None, finalize):
        return self.decoder_wrapper.decode(samp_freq, samples.shape[0], <float *> samples.data, finalize)

    def get_decoded_string(self):
        cdef string decoded_string
        cdef double likelihood=0.0
        self.decoder_wrapper.get_decoded_string(decoded_string, likelihood)
        return decoded_string.decode(), likelihood

    def get_word_alignment(self):
        cdef vector[string] words
        cdef vector[int] times
        cdef vector[int] lengths
        if not self.decoder_wrapper.get_word_alignment(words, times, lengths):
            return None
        return words, times, lengths
