AC_INIT([voice2json], [0.2.0], [mike@rhasspy.org])
AC_CONFIG_MACRO_DIR([m4])
PC_INIT([3.7.0])

dnl ---------------------------------------------------------------------------

AC_PREFIX_DEFAULT([$PWD/.venv])

dnl Template files to write
AC_CONFIG_FILES([Makefile])
AC_CONFIG_FILES([setup.py])
AC_CONFIG_FILES([voice2json.sh])

AC_CANONICAL_HOST
AC_PROG_INSTALL
AC_PROG_MKDIR_P

dnl ---------------------------------------------------------------------------

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
kaldi_arch=NONE
kaldi_from=prebuilt

is_julius_enabled=UNKNOWN
julius_arch=NONE
julius_from=prebuilt

is_deepspeech_enabled=UNKNOWN
deepspeech_arch=NONE
deepspeech_from=prebuilt

dnl --------------
dnl Training Tools
dnl --------------

is_training_enabled=yes

is_opengrm_enabled=UNKNOWN
opengrm_arch=NONE
opengrm_from=prebuilt

is_phonetisaurus_enabled=UNKNOWN
phonetisaurus_arch=NONE
phonetisaurus_from=prebuilt

is_kenlm_enabled=UNKNOWN
kenlm_arch=NONE
kenlm_from=prebuilt

dnl Set architectures based on host CPU
AS_CASE([$host_cpu],
    [armv6l],[
        dnl ARM 32-bit v6 (Pi 1/0)
        docker_arch=armv6

        is_precise_enabled=no
        precise_from=NONE

        is_kaldi_enabled=no
        kaldi_from=NONE

        is_julius_enabled=no
        julius_from=source

        is_deepspeech_enabled=no
        deepspeech_from=NONE

        is_opengrm_enabled=yes
        opengrm_arch=armv6l

        is_phonetisaurus_enabled=yes
        phonetisaurus_arch=armv6l

        is_kenlm_enabled=no
        kenlm_from=source
    ],
    [armv7l],[
        dnl ARM 32-bit v7 (Pi 2/3/4)
        docker_arch=armv7

        is_precise_enabled=yes
        precise_arch=armv7l

        is_kaldi_enabled=yes
        kaldi_arch=armv7

        is_julius_enabled=yes
        julius_arch=armv7

        is_deepspeech_enabled=yes
        deepspeech_arch=rpi3

        is_opengrm_enabled=yes
        opengrm_arch=armhf

        is_phonetisaurus_enabled=yes
        phonetisaurus_arch=armhf

        is_kenlm_enabled=yes
        kenlm_arch=armv7
    ],
    [aarch64],[
        dnl ARM 64-bit (Pi 3/4)
        docker_arch=arm64

        is_precise_enabled=yes
        precise_arch=aarch64

        is_kaldi_enabled=yes
        kaldi_arch=arm64

        is_julius_enabled=no
        julius_from=source

        is_deepspeech_enabled=no
        deepspeech_from=NONE

        is_opengrm_enabled=yes
        opengrm_arch=aarch64

        is_phonetisaurus_enabled=yes
        phonetisaurus_arch=arm64

        is_kenlm_enabled=no
        kenlm_from=source
    ],
    [x86_64],[
        dnl x86_64 compatible
        docker_arch=amd64

        is_precise_enabled=yes
        precise_arch=x86_64

        is_kaldi_enabled=yes
        kaldi_arch=amd64

        is_julius_enabled=yes
        julius_arch=amd64

        is_deepspeech_enabled=yes
        deepspeech_arch=amd64

        is_opengrm_enabled=yes
        opengrm_arch=amd64

        is_phonetisaurus_enabled=yes
        phonetisaurus_arch=amd64

        is_kenlm_enabled=yes
        kenlm_arch=amd64
    ])

dnl ---------------------------------------------------------------------------

precompiled_binaries_enabled=yes

AC_ARG_ENABLE([precompiled-binaries],
    AS_HELP_STRING([--disable-precompiled-binaries],
        [build dependencies from source instead of downloading prebuilt binaries]))

AC_ARG_VAR([VOICE2JSON_LANGUAGE],
    [use recommended settings for specific language (ca,nl,en,fr,de,el,hi,it,kz,zh,pl,pt,es,sv,vi)])

dnl ---------------------------------------------------------------------------
dnl Python virtual environment
dnl ---------------------------------------------------------------------------

is_virtualenv_enabled=yes

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

dnl Override with recommended settings for language
AS_IF([test "x$VOICE2JSON_LANGUAGE" != x],
    [
        lang=$VOICE2JSON_LANGUAGE
        AS_CASE([$lang],
            [ca],[stt_system=pocketsphinx],
            [nl],[stt_system=kaldi],
            [en],[stt_system=kaldi],
            [fr],[stt_system=kaldi],
            [de],[stt_system=kaldi],
            [hi],[stt_system=pocketsphinx],
            [it],[stt_system=pocketsphinx],
            [kz],[stt_system=pocketsphinx],
            [zh],[stt_system=pocketsphinx],
            [pl],[stt_system=julius],
            [pt],[stt_system=pocketsphinx],
            [ru],[stt_system=pocketsphinx],
            [es],[stt_system=pocketsphinx],
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
AS_IF([$enable_precompiled_binaries],
      [no],[
          kaldi_from=source
          opengrm_from=source
          phonetisaurus_from=source
          kenlm_from=source
      ])

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
AS_ECHO(["  kaldi: ${is_kaldi_enabled} (${kaldi_arch}, ${kaldi_from})"]),
AS_ECHO(["  kaldi: ${is_kaldi_enabled}"]))


AS_IF([test "x$is_deepspeech_enabled" = xyes],
AS_ECHO(["  deepspeech: ${is_deepspeech_enabled} (${deepspeech_arch}, ${deepspeech_from})"]),
AS_ECHO(["  deepspeech: ${is_deepspeech_enabled}"]))

AS_ECHO(["
training:"])

AS_IF([test "x$is_opengrm_enabled" = xyes],
AS_ECHO(["  opengrm: ${is_opengrm_enabled} (${opengrm_arch}, ${opengrm_from})"]),
AS_ECHO(["  opengrm: ${is_opengrm_enabled}"]))

AS_IF([test "x$is_phonetisaurus_enabled" = xyes],
AS_ECHO(["  phonetisaurus: ${is_phonetisaurus_enabled} (${phonetisaurus_arch}, ${phonetisaurus_from})"]),
AS_ECHO(["  phonetisaurus: ${is_phonetisaurus_enabled}"]))

AS_IF([test "x$is_kenlm_enabled" = xyes],
AS_ECHO(["  kenlm: ${is_kenlm_enabled} (${kenlm_arch}, ${kenlm_from})"]),
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

AC_SUBST([KALDI_ARCH], [$kaldi_arch])
AC_SUBST([ENABLE_KALDI], [$is_kaldi_enabled])
AC_SUBST([KALDI_FROM], [$kaldi_from])

AC_SUBST([JULIUS_ARCH], [$julius_arch])
AC_SUBST([ENABLE_JULIUS], [$is_julius_enabled])
AC_SUBST([JULIUS_FROM], [$julius_from])

AC_SUBST([DEEPSPEECH_ARCH], [$deepspeech_arch])
AC_SUBST([ENABLE_DEEPSPEECH], [$is_deepspeech_enabled])
AC_SUBST([DEEPSPEECH_FROM], [$deepspeech_from])

AC_SUBST([OPENGRM_ARCH], [$opengrm_arch])
AC_SUBST([ENABLE_OPENGRM], [$is_opengrm_enabled])
AC_SUBST([OPENGRM_FROM], [$opengrm_from])

AC_SUBST([PHONETISAURUS_ARCH], [$phonetisaurus_arch])
AC_SUBST([ENABLE_PHONETISAURUS], [$is_phonetisaurus_enabled])
AC_SUBST([PHONETISAURUS_FROM], [$phonetisaurus_from])

AC_SUBST([KENLM_ARCH], [$kenlm_arch])
AC_SUBST([ENABLE_KENLM], [$is_kenlm_enabled])
AC_SUBST([KENLM_FROM], [$kenlm_from])

AC_OUTPUT
