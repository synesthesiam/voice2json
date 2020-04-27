AC_INIT([voice2json], [0.2.0])
AC_CONFIG_MACRO_DIR([m4])
PC_INIT([3.7.0])

dnl ---------------------------------------------------------------------------

dnl Template files to write
AC_CONFIG_FILES([Makefile])
AC_CONFIG_FILES([setup.py])

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
    AS_HELP_STRING([--disable-precompiled-binaries],
        [build from source instead of downloading pre-compiled binaries for dependencies]),, [
    AS_CASE([$host_cpu],
        dnl Enable by default on supported architectures.
        dnl TODO: Ensure platform is linux.
        [x86_64|armv6l|armv7l|aarch64],[enable_precompiled_binaries=yes],
        [enable_precompiled_binaries=no])
])

AS_IF([test "x$enable_precompiled_binaries" != xno], [
    AC_MSG_NOTICE([using pre-compiled binaries])
    AC_SUBST([ENABLE_PRECOMPILED_BINARIES], [yes])
])

dnl ---------------------------------------------------------------------------
dnl Python virtual environment
dnl ---------------------------------------------------------------------------

AC_ARG_WITH([virtualenv],
    [AS_HELP_STRING([--with-virtualenv], [install to a Python virtual environment])],,
    [with_virtualenv=yes])

AS_IF([test "x$with_virtualenv" != xno], [
    AC_MSG_NOTICE([installing to virtual environment])
    AC_SUBST([VIRTUALENV], [yes])
])

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
AC_ARG_ENABLE([wake],
    AS_HELP_STRING([--disable-training],
        [disable installation of training tools]))

AS_IF([test "x$enable_training" == xno], [
    enable_opengrm=no
    enable_phonetisaurus=no
    AC_MSG_NOTICE([training is disabled])
])

AS_IF([test "x$enable_opengrm" != xno], [
    AC_SUBST([ENABLE_OPENGRM], [yes])
    AC_MSG_NOTICE([opengrm is enabled])
])

AS_IF([test "x$enable_phonetisaurus" != xno], [
    AC_SUBST([ENABLE_PHONETISAURUS], [yes])
    AC_MSG_NOTICE([phonetisaurus is enabled])
])

dnl ---------------------------------------------------------------------------
dnl Wake Word Systems
dnl ---------------------------------------------------------------------------

AS_CASE([$host_cpu],
    dnl Disable precise by default on Pi Zero
    [x86_64|armv7l|aarch64],[enable_precise=yes],
    [enable_precise=no])

dnl Mycroft Precise
AC_ARG_ENABLE([precise],
    AS_HELP_STRING([--disable-precise],
        [disable installation of Mycroft Precise wake word system]))

dnl Wake meta
AC_ARG_ENABLE([wake],
    AS_HELP_STRING([--disable-wake],
        [disable installation of all wake word systems]))

AS_IF([test "x$enable_wake" == xno], [
    enable_precise=no
    AC_MSG_NOTICE([wake is disabled])
])

AS_IF([test "x$enable_precise" != xno], [
    AC_SUBST([ENABLE_PRECISE], [yes])
    AC_SUBST([PRECISE_ARCH], [$host_cpu])
    AC_MSG_NOTICE([precise is enabled])
])


dnl ---------------------------------------------------------------------------
dnl Speech to Text Systems
dnl ---------------------------------------------------------------------------

dnl Pocketsphinx
AC_ARG_ENABLE([pocketsphinx],
    AS_HELP_STRING([--disable-pocketsphinx],
        [disable installation of pocketsphinx speech to text system]))

dnl Speech to text meta
AC_ARG_ENABLE([speech_to_text],
    AS_HELP_STRING([--disable-speech-to-text],
        [disable installation of all speech to text systems]))

AS_IF([test "x$enable_speech_to_text" == xno], [
    enable_pocketsphinx=no
    enable_kaldi=no
    enable_deepspeech=no
    enable_julius=no
    AC_MSG_NOTICE([speech to text is disabled])
])

AS_IF([test "x$enable_pocketsphinx" != xno], [
    AC_SUBST([ENABLE_POCKETSPHINX], [yes])
    dnl Check for Swig (TODO: portaudio)
    AX_PKG_SWIG([3.0.12])
    AC_MSG_NOTICE([pocketsphinx is enabled])
])

dnl Kaldi
AC_ARG_ENABLE([kaldi],
    AS_HELP_STRING([--enable-kaldi], [enable installation of Kaldi speech to text system]),, [
    AS_CASE([$host_cpu],
        dnl Disable by default on Pi Zero
        [x86_64|armv7l|aarch64],[enable_kaldi=yes],
        [enable_kaldi=no])
])

AS_IF([test "x$enable_kaldi" != xno], [
    AC_SUBST([ENABLE_KALDI], [yes])
    AS_CASE([$host_cpu],
        [armv7l],[kaldi_arch=armv7],
        [aarch64],[kaldi_arch=arm64],
        [kaldi_arch=amd64])
    AC_SUBST([KALDI_ARCH], [$kaldi_arch])
    AC_MSG_NOTICE([kaldi is enabled])
])

dnl Julius
AC_CHECK_PROG([HAS_JULIUS], [julius],[yes],[no])
AS_IF([test "x$HAS_JULIUS" != xno], [
    enable_julius=no
])

AC_ARG_ENABLE([julius],
    AS_HELP_STRING([--enable-julius], [enable installation of julius speech to text system]),, [
        AS_CASE([$host_cpu],
        dnl Disable by default on Pi Zero and arm64
        [x86_64|armv7l],[enable_julius=yes],
        [enable_julius=no])
])

AS_IF([test "x$enable_julius" != xno], [
    AC_SUBST([ENABLE_JULIUS], [yes])
    AC_SUBST([JULIUS_ARCH], [$docker_arch])
    AC_MSG_NOTICE([julius is enabled])
])

dnl Mozilla's DeepSpeech
AC_ARG_ENABLE([deepspeech],
    AS_HELP_STRING([--enable-deepspeech], [enable installation of deepspeech speech to text system]),, [
    AS_CASE([$host_cpu],
        dnl Disable by default on Pi Zero and arm64
        [x86_64|armv7l],[enable_deepspeech=yes],
        [enable_deepspeech=no])
])

AS_IF([test "x$enable_deepspeech" != xno], [
    AC_SUBST([ENABLE_DEEPSPEECH], [yes])

    dnl build_binary from KenLM
    AC_CHECK_PROG([HAS_BUILD_BINARY], [build_binary],[yes],[no])

    dnl generate_trie from DeepSpeech native client
    AC_CHECK_PROG([HAS_GENERATE_TRIE], [generate_trie],[yes],[no])

    AS_CASE([$host_cpu],
        [armv7l],[
            deepspeech_arch=rpi3
            kenlm_arch=armv7
        ],
        [
            deepspeech_arch=amd64
            kenlm_arch=amd64
        ])

    AC_SUBST([DEEPSPEECH_ARCH], [$deepspeech_arch])
    AC_SUBST([KENLM_ARCH], [$kenlm_arch])
    AC_MSG_NOTICE([deepspeech is enabled])
])

dnl ---------------------------------------------------------------------------

AC_OUTPUT
