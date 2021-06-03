AC_INIT([voice2json], [2.1.0], [mike@rhasspy.org])
AC_CONFIG_MACRO_DIR([m4])
PC_INIT([3.7.0])

dnl ---------------------------------------------------------------------------

AC_PREFIX_DEFAULT([$PWD/.venv])

dnl Template files to write
AC_CONFIG_FILES([Makefile])
AC_CONFIG_FILES([setup.py])
AC_CONFIG_FILES([voice2json.sh])
AC_CONFIG_FILES([voice2json.spec])

AC_CANONICAL_HOST
AC_PROG_INSTALL
AC_PROG_MKDIR_P
AC_PROG_CC
AC_PROG_CXX

dnl ---------------------------------------------------------------------------

is_virtualenv_enabled=yes
is_dependency_check_enabled=yes

dnl An in-place install does not include voice2json Python modules, since they will
dnl be used directly from source.
is_in_place=no

dnl -------------------
dnl Wake Word Detection
dnl -------------------

is_wake_enabled=yes

is_precise_enabled=UNKNOWN
precise_arch=NONE
precise_from=prebuilt

dnl --------------
dnl Speech to Text
dnl --------------

is_speech_to_text_enabled=yes

is_pocketsphinx_enabled=UNKNOWN
pocketsphinx_from=source

is_kaldi_enabled=UNKNOWN
kaldi_from=prebuilt

is_julius_enabled=UNKNOWN
julius_from=prebuilt

is_deepspeech_enabled=UNKNOWN
deepspeech_arch=NONE
deepspeech_from=prebuilt

dnl --------------
dnl Training Tools
dnl --------------

is_training_enabled=yes

is_opengrm_enabled=UNKNOWN
opengrm_from=prebuilt

is_phonetisaurus_enabled=UNKNOWN
phonetisaurus_from=prebuilt

is_kenlm_enabled=UNKNOWN
kenlm_from=prebuilt

dnl Set architectures based on host CPU
AS_CASE([$host_cpu],
    [armv6l],[
        dnl ARM 32-bit v6 (Pi 1/0)
        docker_arch=armv6

        is_precise_enabled=no
        precise_from=NONE

        is_pocketsphinx_enabled=yes
        pocketsphinx_from=source

        is_kaldi_enabled=no
        kaldi_from=NONE

        is_julius_enabled=yes

        is_deepspeech_enabled=no
        deepspeech_from=NONE

        is_opengrm_enabled=yes

        is_phonetisaurus_enabled=yes

        is_kenlm_enabled=yes
    ],
    [armv7l],[
        dnl ARM 32-bit v7 (Pi 2/3/4)
        docker_arch=armv7

        is_precise_enabled=yes
        precise_arch=armv7l

        is_pocketsphinx_enabled=yes
        pocketsphinx_from=source

        is_kaldi_enabled=yes

        is_julius_enabled=yes

        is_deepspeech_enabled=yes
        deepspeech_arch=rpi3

        is_opengrm_enabled=yes

        is_phonetisaurus_enabled=yes

        is_kenlm_enabled=yes
    ],
    [aarch64],[
        dnl ARM 64-bit (Pi 3/4)
        docker_arch=arm64

        is_precise_enabled=yes
        precise_arch=aarch64

        is_pocketsphinx_enabled=yes
        pocketsphinx_from=source

        is_kaldi_enabled=yes

        is_julius_enabled=yes

        is_deepspeech_enabled=no
        deepspeech_from=NONE

        is_opengrm_enabled=yes

        is_phonetisaurus_enabled=yes

        dnl Don't bother since DeepSpeech is not supported
        is_kenlm_enabled=no
    ],
    [x86_64],[
        dnl x86_64 compatible
        docker_arch=amd64

        is_precise_enabled=yes
        precise_arch=x86_64

        is_pocketsphinx_enabled=yes
        pocketsphinx_from=source

        is_kaldi_enabled=yes

        is_julius_enabled=yes

        is_deepspeech_enabled=yes
        deepspeech_arch=amd64

        is_opengrm_enabled=yes

        is_phonetisaurus_enabled=yes

        is_kenlm_enabled=yes
    ])

dnl ---------------------------------------------------------------------------

AC_ARG_ENABLE([in-place],
    AS_HELP_STRING([--enable-in-place],
        [use shared files directly from source directory instead of copying them]))

precompiled_binaries_enabled=yes

AC_ARG_ENABLE([precompiled-binaries],
    AS_HELP_STRING([--disable-precompiled-binaries],
        [build dependencies from source instead of downloading prebuilt binaries]))

AC_ARG_VAR([VOICE2JSON_LANGUAGE],
    [use recommended settings for specific language (ca,cs,nl,en,fr,de,el,hi,it,kz,zh,pl,pt,es,sv,vi)])

dnl ---------------------------------------------------------------------------
dnl Python virtual environment
dnl ---------------------------------------------------------------------------

AC_ARG_ENABLE([virtualenv],
    [AS_HELP_STRING([--disable-virtualenv],
        [don't create a Python virtual environment at prefix])])

AC_ARG_VAR([VIRTUALENV_FLAGS], [flags to pass to when creating virtual environment])

dnl ---------------------------------------------------------------------------
dnl Training Tools
dnl ---------------------------------------------------------------------------

dnl Opengrm
AC_ARG_ENABLE([opengrm],
    AS_HELP_STRING([--disable-opengrm],
        [disable installation of opengrm language modeling toolkit]))

dnl Phonetisaurus
AC_ARG_ENABLE([phonetisaurus],
    AS_HELP_STRING([--disable-phonetisaurus],
        [disable installation of phonetisaurus grapheme to phoneme tool]))

dnl Training meta
AC_ARG_ENABLE([training],
    AS_HELP_STRING([--disable-training],
        [disable installation of training tools]))

dnl ---------------------------------------------------------------------------
dnl Wake Word Systems
dnl ---------------------------------------------------------------------------

dnl Mycroft Precise
AC_ARG_ENABLE([precise],
    AS_HELP_STRING([--disable-precise],
        [disable installation of Mycroft Precise wake word system]))

dnl Wake meta
AC_ARG_ENABLE([wake],
    AS_HELP_STRING([--disable-wake],
        [disable installation of all wake word systems]))

dnl ---------------------------------------------------------------------------
dnl Speech to Text Systems
dnl ---------------------------------------------------------------------------

dnl Pocketsphinx
AC_ARG_ENABLE([pocketsphinx],
    AS_HELP_STRING([--disable-pocketsphinx],
    [disable installation of pocketsphinx speech to text system]))

dnl Kaldi
AC_ARG_ENABLE([kaldi],
    AS_HELP_STRING([--disable-kaldi],
        [disable installation of Kaldi speech to text system]))

dnl Julius
AC_ARG_ENABLE([julius],
    AS_HELP_STRING([--disable-julius],
        [disable installation of julius speech to text system]))

dnl Mozilla's DeepSpeech
AC_ARG_ENABLE([deepspeech],
    AS_HELP_STRING([--disable-deepspeech],
        [disable installation of deepspeech speech to text system]))

dnl Speech to text meta
AC_ARG_ENABLE([speech-to-text],
    AS_HELP_STRING([--disable-speech-to-text],
        [disable installation of all speech to text systems]))

AC_ARG_VAR([VOICE2JSON_SPEECH_SYSTEM],
    AS_HELP_STRING([only enable a single speech to text system (pocketsphinx,kaldi,julius,deepspeech)]))

dnl ---------------------------------------------------------------------------
dnl Resolve Settings
dnl ---------------------------------------------------------------------------

stt_system=NONE

kaldi_or_pocketsphinx=kaldi
AS_IF([test "x${is_kaldi_enabled}" != xyes],
    [kaldi_or_pocketsphinx=pocketsphinx])

dnl Override with recommended settings for language
AS_IF([test "x$VOICE2JSON_LANGUAGE" != x],
    [
        lang=$VOICE2JSON_LANGUAGE
        AS_CASE([$lang],
            [ca],[stt_system=pocketsphinx],
            [cs],[stt_system=kaldi],
            [nl],[stt_system=${kaldi_or_pocketsphinx}],
            [en],[stt_system=${kaldi_or_pocketsphinx}],
            [fr],[stt_system=${kaldi_or_pocketsphinx}],
            [de],[stt_system=${kaldi_or_pocketsphinx}],
            [hi],[stt_system=pocketsphinx],
            [it],[stt_system=deepspeech],
            [kz],[stt_system=pocketsphinx],
            [zh],[stt_system=pocketsphinx],
            [pl],[stt_system=deepspeech],
            [pt],[stt_system=pocketsphinx],
            [ru],[stt_system=${kaldi_or_pocketsphinx}],
            [es],[stt_system=${kaldi_or_pocketsphinx}],
            [sv],[stt_system=kaldi],
            [vi],[stt_system=kaldi],
            [AC_MSG_ERROR([Unsupported language: $lang])])

    ])


dnl Override with specific speech to text system
AS_IF([test "x$VOICE2JSON_SPEECH_SYSTEM" != x],
    [stt_system=$VOICE2JSON_SPEECH_SYSTEM])

AS_CASE([$stt_system],
        [pocketsphinx],
        [
            is_pocketsphinx_enabled=yes
            is_kaldi_enabled=no
            is_julius_enabled=no
            is_deepspeech_enabled=no
        ],
        [kaldi],
        [
            is_pocketsphinx_enabled=no
            is_kaldi_enabled=yes
            is_julius_enabled=no
            is_deepspeech_enabled=no
        ],
        [julius],
        [
            is_pocketsphinx_enabled=no
            is_kaldi_enabled=no
            is_julius_enabled=yes
            is_deepspeech_enabled=no
        ],
        [deepspeech],
        [
            is_pocketsphinx_enabled=no
            is_kaldi_enabled=no
            is_julius_enabled=no
            is_deepspeech_enabled=yes
        ])

dnl Disable tools that are only applicable to specific speech to text systems
AS_IF([test "x${is_deepspeech_enabled}x${is_pocketsphinx_enabled}x${is_kaldi_enabled}x${is_julius_enabled}" = xyesxnoxnoxno],
    [is_phonetisaurus_enabled=no])

AS_IF([test "x${is_deepspeech_enabled}" = xno],
    [is_kenlm_enabled=no])

dnl Override with enable/disable options (meta)
AS_CASE([$enable_wake],
        [no],[is_precise_enabled=no])

AS_CASE([$enable_speech_to_text],
        [no],[
            is_pocketsphinx_enabled=no
            is_kaldi_enabled=no
            is_julius_enabled=no
            is_deepspeech_enabled=no
        ])

AS_CASE([$enable_training],
        [no],[
            is_opengrm_enabled=no
            is_phonetisaurus_enabled=no
            is_kenlm_enabled=no
        ])

dnl Override with enable/disable options (non-meta)
AS_CASE([$enable_precise],
    [yes],[is_precise_enabled=yes],
    [no],[is_precise_enabled=no])

AS_CASE([$enable_pocketsphinx],
        [yes],[is_pocketsphinx_enabled=yes],
        [no],[is_pocketsphinx_enabled=no])

AS_CASE([$enable_kaldi],
        [yes],[is_kaldi_enabled=yes],
        [no],[is_kaldi_enabled=no])

AS_CASE([$enable_julius],
        [yes],[is_julius_enabled=yes],
        [no],[is_julius_enabled=no])

AS_CASE([$enable_deepspeech],
        [yes],[is_deepspeech_enabled=yes],
        [no],[is_deepspeech_enabled=no])

AS_CASE([$enable_opengrm],
    [yes],[is_opengrm_enabled=yes],
    [no],[is_opengrm_enabled=no])

AS_CASE([$enable_phonetisaurus],
    [yes],[is_phonetisaurus_enabled=yes],
    [no],[is_phonetisaurus_enabled=no])

AS_CASE([$enable_kenlm],
        [yes],[is_kenlm_enabled=yes],
        [no],[is_kenlm_enabled=no])

dnl Determine prebuilt/source
AS_CASE([$enable_precompiled_binaries],
        [no],[
            kaldi_from=source
            opengrm_from=source
            phonetisaurus_from=source
            kenlm_from=source
        ])

dnl In-place install
AS_CASE([$enable_in_place],
        [yes],[is_in_place=yes],
        [no],[is_in_place=no])

dnl Virtual environment
AS_CASE([$enable_virtualenv],
        [yes],[is_virtualenv_enabled=yes],
        [no],[is_virtualenv_enabled=no])

dnl ---------------------------------------------------------------------------
dnl Extra Dependency Checks
dnl ---------------------------------------------------------------------------

AC_ARG_ENABLE([dependency-check],
    AS_HELP_STRING([--disable-dependency-check],
        [disable checking for external dependencies]),
    [is_dependency_check_enabled=$enableval])

AS_IF([test "x$is_dependency_check_enabled" = xyes], [

dnl precise-runner depends on PyAudio, which requires portaudio.h
AS_IF([test "x$is_precise_enabled" = xyes],
    [
        AC_CHECK_HEADER([portaudio.h], [], [
            AC_MSG_ERROR([portaudio development libary is required for Mycroft Precise (portaudio19-dev package)])
        ])
    ])

dnl pocketsphinx needs swig and a C compiler
AS_IF([test "x${is_pocketsphinx_enabled}x${pocketsphinx_from}" = xyesxsource],
    [
        AS_IF([test "x$CC" = x], [
            AC_MSG_ERROR([C compiler is required for Pocketsphinx (build-essential package)])
        ])

        AX_PKG_SWIG([3.0.0], [], [
            AC_MSG_ERROR([swig is required for Pocketsphinx (swig package)])
        ])
    ])

dnl julius needs a C compiler
AS_IF([test "x${is_julius_enabled}x${julius_from}" = xyesxsource],
    [
        AS_IF([test "x$CC" = x], [
            AC_MSG_ERROR([C compiler is required for Julius (build-essential package)])
        ])
    ])

dnl kaldi needs ATLAS
AS_IF([test "x$is_kaldi_enabled" = xyes],
    [
        AC_CHECK_LIB(atlas, ATL_xerbla, [], [
            AC_MSG_ERROR([ATLAS is required for Kaldi (libatlas-base-dev package)])
        ])
    ])

dnl kaldi needs a C++ compiler (and a ton of other things)
AS_IF([test "x${is_kaldi_enabled}x${kaldi_from}" = xyesxsource],
    [
        AS_IF([test "x$CXX" = x], [
            AC_MSG_ERROR([C++ compiler is required for Kaldi (build-essential package)])
        ])
    ])

])  dnl is_dependency_check_enabled

dnl ---------------------------------------------------------------------------
dnl Summary
dnl ---------------------------------------------------------------------------

dnl Prefix is NONE for some reason instead of default value
summary_prefix=$prefix
AS_IF([test "x$summary_prefix" = xNONE], [
    summary_prefix=$PWD/.venv
])

AS_ECHO(["
voice2json configuration summary:

architecture: ${host_cpu}/${docker_arch}
prefix: ${summary_prefix}
virtualenv: ${is_virtualenv_enabled}
in place: ${is_in_place}
language: ${VOICE2JSON_LANGUAGE}

wake:"])

AS_IF([test "x$is_precise_enabled" = xyes],
AS_ECHO(["  mycroft precise: ${is_precise_enabled} (${precise_arch}, ${precise_from})"]),
AS_ECHO(["  mycroft precise: ${is_precise_enabled}"]))

AS_ECHO(["
speech to text:"])

AS_IF([test "x$is_pocketsphinx_enabled" = xyes],
AS_ECHO(["  pocketsphinx: ${is_pocketsphinx_enabled} (${pocketsphinx_from})"]),
AS_ECHO(["  pocketsphinx: ${is_pocketsphinx_enabled}"]))

AS_IF([test "x$is_kaldi_enabled" = xyes],
AS_ECHO(["  kaldi: ${is_kaldi_enabled} (${kaldi_from})"]),
AS_ECHO(["  kaldi: ${is_kaldi_enabled}"]))

AS_IF([test "x$is_julius_enabled" = xyes],
AS_ECHO(["  julius: ${is_julius_enabled} (${julius_from})"]),
AS_ECHO(["  julius: ${is_julius_enabled}"]))

AS_IF([test "x$is_deepspeech_enabled" = xyes],
AS_ECHO(["  deepspeech: ${is_deepspeech_enabled} (${deepspeech_arch}, ${deepspeech_from})"]),
AS_ECHO(["  deepspeech: ${is_deepspeech_enabled}"]))

AS_ECHO(["
training:"])

AS_IF([test "x$is_opengrm_enabled" = xyes],
AS_ECHO(["  opengrm: ${is_opengrm_enabled} (${opengrm_from})"]),
AS_ECHO(["  opengrm: ${is_opengrm_enabled}"]))

AS_IF([test "x$is_phonetisaurus_enabled" = xyes],
AS_ECHO(["  phonetisaurus: ${is_phonetisaurus_enabled} (${phonetisaurus_from})"]),
AS_ECHO(["  phonetisaurus: ${is_phonetisaurus_enabled}"]))

AS_IF([test "x$is_kenlm_enabled" = xyes],
AS_ECHO(["  kenlm: ${is_kenlm_enabled} (${kenlm_from})"]),
AS_ECHO(["  kenlm: ${is_kenlm_enabled}"]))

AS_ECHO([""])

dnl ---------------------------------------------------------------------------
dnl Output
dnl ---------------------------------------------------------------------------

AC_SUBST([VIRTUALENV], [$is_virtualenv_enabled])

AC_SUBST([DOCKER_ARCH], [$docker_arch])

AC_SUBST([PRECISE_ARCH], [$precise_arch])
AC_SUBST([ENABLE_PRECISE], [$is_precise_enabled])
AC_SUBST([PRECISE_FROM], [$precise_from])

AC_SUBST([ENABLE_POCKETSPHINX], [$is_pocketsphinx_enabled])
AC_SUBST([POCKETSPHINX_FROM], [$pocketsphinx_from])

AC_SUBST([ENABLE_KALDI], [$is_kaldi_enabled])
AC_SUBST([KALDI_FROM], [$kaldi_from])

AC_SUBST([ENABLE_JULIUS], [$is_julius_enabled])
AC_SUBST([JULIUS_FROM], [$julius_from])

AC_SUBST([DEEPSPEECH_ARCH], [$deepspeech_arch])
AC_SUBST([ENABLE_DEEPSPEECH], [$is_deepspeech_enabled])
AC_SUBST([DEEPSPEECH_FROM], [$deepspeech_from])

AC_SUBST([ENABLE_OPENGRM], [$is_opengrm_enabled])
AC_SUBST([OPENGRM_FROM], [$opengrm_from])

AC_SUBST([ENABLE_PHONETISAURUS], [$is_phonetisaurus_enabled])
AC_SUBST([PHONETISAURUS_FROM], [$phonetisaurus_from])

AC_SUBST([ENABLE_KENLM], [$is_kenlm_enabled])
AC_SUBST([KENLM_FROM], [$kenlm_from])

AC_SUBST([IN_PLACE], [$is_in_place])

AC_OUTPUT
