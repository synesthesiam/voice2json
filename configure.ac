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

dnl Set docker-compatiable architecture
AS_CASE([$host_cpu],
    [armv6l],[docker_arch=armv6],
    [armv7l],[docker_arch=armv7],
    [aarch64],[docker_arch=arm64],
    [docker_arch=amd64])

AC_SUBST([DOCKER_ARCH], [$docker_arch])

dnl ---------------------------------------------------------------------------

AC_ARG_ENABLE([precompiled-binaries],
    AS_HELP_STRING([--enable-precompiled-binaries],
        [download pre-compiled binaries for dependencies instead of building from source]),
    [enable_precompiled_binaries=$enableval],
    [
        dnl Enable by default on supported CPUs
        AS_CASE([$host_cpu],
            dnl TODO: Ensure platform is linux.
            [x86_64|armv6l|armv7l|aarch64],[enable_precompiled_binaries=yes],
            [enable_precompiled_binaries=no])
])

AC_SUBST([ENABLE_PRECOMPILED_BINARIES], [$enable_precompiled_binaries])

dnl ---------------------------------------------------------------------------
dnl Python virtual environment
dnl ---------------------------------------------------------------------------

AC_ARG_WITH([virtualenv],
    [AS_HELP_STRING([--with-virtualenv], [install to a Python virtual environment])],
    [with_virtualenv=$enableval],
    [with_virtualenv=yes])

AC_SUBST([VIRTUALENV], [$with_virtualenv])
AS_IF([test "x$with_virtualenv" != xno], [
    AC_MSG_NOTICE([installing to virtual environment])
])

AC_ARG_VAR([VIRTUALENV_FLAGS], [flags to pass to when creating virtual environment])

dnl ---------------------------------------------------------------------------
dnl Training Tools
dnl ---------------------------------------------------------------------------

dnl Opengrm
AC_ARG_ENABLE([opengrm],
    AS_HELP_STRING([--enable-opengrm],
        [enable installation of opengrm language modeling toolkit]),
    [enable_opengrm=$enableval],
    [enable_opengrm=yes])

AS_CASE([$host_cpu],
    [armv6l],[opengrm_arch=armv6l],
    [armv7l],[opengrm_arch=armhf],
    [aarch64],[opengrm_arch=aarch64],
    [opengrm_arch=amd64])

AC_SUBST([ENABLE_OPENGRM], [$enable_opengrm])
AC_SUBST([OPENGRM_ARCH], [$opengrm_arch])

dnl Phonetisaurus
AC_ARG_ENABLE([phonetisaurus],
    AS_HELP_STRING([--enable-phonetisaurus],
        [enable installation of phonetisaurus grapheme to phoneme tool]),
    [enable_phonetisaurus=$enableval],
    [enable_phonetisaurus=yes])

AS_CASE([$host_cpu],
    [armv6l],[phonetisaurus_arch=armv6l],
    [armv7l],[phonetisaurus_arch=armhf],
    [aarch64],[phonetisaurus_arch=arm64],
    [phonetisaurus_arch=amd64])

AC_SUBST([ENABLE_PHONETISAURUS], [$enable_phonetisaurus])
AC_SUBST([PHONETISAURUS_ARCH], [$phonetisaurus_arch])

dnl Training meta
AC_ARG_ENABLE([training],
    AS_HELP_STRING([--enable-training],
        [enable installation of training tools]),
    [
        enable_opengrm=$enableval
        enable_phonetisaurus=$enableval
    ])

dnl ---------------------------------------------------------------------------
dnl Wake Word Systems
dnl ---------------------------------------------------------------------------

dnl Mycroft Precise
AC_ARG_ENABLE([precise],
    AS_HELP_STRING([--enable-precise],
        [enable installation of Mycroft Precise wake word system]),
    [enable_precise=$enableval],
    [
        dnl Enable by default on supported CPUs
        AS_CASE([$host_cpu],
            dnl Disable on Pi Zero
            [x86_64|armv7l|aarch64],[enable_precise=yes],
            [enable_precise=no])
])

precise_arch=$host_cpu
AC_SUBST([ENABLE_PRECISE], [$enable_precise])
AC_SUBST([PRECISE_ARCH], [$precise_arch])

dnl Wake meta
AC_ARG_ENABLE([wake],
    AS_HELP_STRING([--enable-wake],
        [enable installation of all wake word systems]),
    [enable_precise=$enableval])

dnl ---------------------------------------------------------------------------
dnl Speech to Text Systems
dnl ---------------------------------------------------------------------------

dnl Speech to text meta
AC_ARG_ENABLE([speech_to_text],
    AS_HELP_STRING([--enable-speech-to-text],
        [enable installation of all speech to text systems]),
    [
        enable_pocketsphinx=$enableval
        enable_kaldi=$enableval
        enable_deepspeech=$enableval
        enable_julius=$enableval
    ])

AC_ARG_WITH([best_for_language],
    AS_HELP_STRING([--with-best-for-language],
        [choose best settings for specific language (ca,nl,en,fr,de,el,hi,it,kz,zh,pl,pt,es,sv,vi)]),
    [
        lang=$with_best_for_language
        best=none
        AS_CASE([$lang],
            [ca],[best=pocketsphinx],
            [nl],[best=kaldi],
            [en],[best=kaldi],
            [fr],[best=kaldi],
            [de],[best=kaldi],
            [hi],[best=pocketsphinx],
            [it],[best=pocketsphinx],
            [kz],[best=pocketsphinx],
            [zh],[best=pocketsphinx],
            [pl],[best=julius],
            [pt],[best=pocketsphinx],
            [ru],[best=pocketsphinx],
            [es],[best=pocketsphinx],
            [sv],[best=kaldi],
            [vi],[best=kaldi],
            [AC_MSG_ERROR([Unsupported language: $lang])])

        AS_IF([test "x$best" = xpocketsphinx],
        [
            enable_pocketsphinx=yes
            enable_kaldi=no
            enable_deepspeech=no
            enable_julius=no
        ])

        AS_IF([test "x$best" = xkaldi],
        [
            enable_pocketsphinx=no
            enable_kaldi=yes
            enable_deepspeech=no
            enable_julius=no
        ])

        AS_IF([test "x$best" = xjulius],
        [
            enable_pocketsphinx=no
            enable_kaldi=no
            enable_deepspeech=no
            enable_julius=yes
        ])

        AS_IF([test "x$best" = xdeepspeech],
        [
            enable_pocketsphinx=no
            enable_kaldi=no
            enable_deepspeech=yes
            enable_julius=no
        ])
    ])

dnl Pocketsphinx
AC_ARG_ENABLE([pocketsphinx],
    AS_HELP_STRING([--enable-pocketsphinx],
    [enable installation of pocketsphinx speech to text system]),
    [enable_pocketsphinx=$enableval],
    [enable_pocketsphinx=yes])

AC_SUBST([ENABLE_POCKETSPHINX], [$enable_pocketsphinx])

dnl Kaldi
AC_ARG_ENABLE([kaldi],
    AS_HELP_STRING([--enable-kaldi],
        [enable installation of Kaldi speech to text system]),
    [enable_kaldi=$enableval],
    [
        dnl Enable by default on supported CPUs
        AS_CASE([$host_cpu],
            dnl Disable on Pi Zero
            [x86_64|armv7l|aarch64],[enable_kaldi=yes],
            [enable_kaldi=no])
    ])

AS_CASE([$host_cpu],
    [armv7l],[kaldi_arch=armv7],
    [aarch64],[kaldi_arch=arm64],
    [kaldi_arch=amd64])

AC_SUBST([ENABLE_KALDI], [$enable_kaldi])
AC_SUBST([KALDI_ARCH], [$kaldi_arch])

dnl Julius
AC_ARG_ENABLE([julius],
    AS_HELP_STRING([--enable-julius],
        [enable installation of julius speech to text system]),
    [enable_julius=$enableval],
    [
        dnl Enable by default on supported CPUs
        AS_CASE([$host_cpu],
            dnl Disable on Pi Zero and arm64
            [x86_64|armv7l],[enable_julius=yes],
            [enable_julius=no])
    ])

julius_arch=$docker_arch
AC_SUBST([ENABLE_JULIUS], [$enable_julius])
AC_SUBST([JULIUS_ARCH], [$julius_arch])

dnl Mozilla's DeepSpeech
AC_ARG_ENABLE([deepspeech],
    AS_HELP_STRING([--enable-deepspeech],
        [enable installation of deepspeech speech to text system]),
    [
        enable_deepspeech=$enableval
        enable_kenlm=$enableval
    ],
    [
        dnl Enable by default on supported CPUs
        AS_CASE([$host_cpu],
            dnl Disable on Pi Zero and arm64
            [x86_64|armv7l],[
                enable_deepspeech=yes
                enable_kenlm=yes
            ],
            [
                enable_deepspeech=no
                enable_kenlm=no
            ])
    ])

AS_CASE([$host_cpu],
    [armv7l],
    [deepspeech_arch=rpi3
     kenlm_arch=armv7],
    [deepspeech_arch=amd64
     kenlm_arch=amd64])

AC_SUBST([ENABLE_DEEPSPEECH], [$enable_deepspeech])
AC_SUBST([ENABLE_KENLM], [$enable_kenlm])
AC_SUBST([DEEPSPEECH_ARCH], [$deepspeech_arch])
AC_SUBST([KENLM_ARCH], [$kenlm_arch])

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
virtualenv: ${with_virtualenv}
pre-compiled binaries: ${enable_precompiled_binaries}

wake:
  mycroft precise: ${enable_precise} ($precise_arch)

speech to text:
  pocketsphinx: ${enable_pocketsphinx}
  kaldi: ${enable_kaldi} ($kaldi_arch)
  deepspeech: ${enable_deepspeech} ($deepspeech_arch)
    kenlm: ${enable_kenlm} ($kenlm_arch)

training:
  opengrm: ${enable_opengrm} (${opengrm_arch})
  phonetisaurus: ${enable_phonetisaurus} (${phonetisaurus_arch})
"])

dnl ---------------------------------------------------------------------------

AC_OUTPUT
