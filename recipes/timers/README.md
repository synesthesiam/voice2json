# Set and Run Timers

Waits for a "wake up" message over MQTT, then records a voice command like "set a timer for five minutes". Waits for the requested amount of time, and responds with a beep and an MQTT message.

## Setup

This recipes assumes you have the `mosquitto_sub` and `mosquitto_pub` commands available. They can be installed with:

```bash
$ sudo apt-get install mosquitto-clients
```

Once you have `voice2json` installed and a profile downloaded, copy `sentences.ini` into your profile directory (probably `$HOME/.config/voice2json`). Make sure to backup your profile first if you've done any customization!

Next, run the `listen_timer` script:

```bash
$ ./listen_timer.sh
```

The script is waiting for an MQTT message on the `timer/wake-up` topic. You could send this from a [Node-RED](https://nodered.org) flow or other IoT software. For now, we'll just use `mosquitto_pub`.

From a terminal, run:

```bash
$ mosquitto_pub -t 'timer/wake-up' -m ''
```

You should hear a beep from `listen_timer.sh`. Now say a command like "set a timer for five seconds". After 5 seconds, you should an alarm sound played (three short beeps). An MQTT message should also have been published to `timer/alarm`.
