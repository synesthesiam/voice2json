# voice2json Web Interface

Provides a basic local web interface on top of the `voice2json` command line. 

You must have `voice2json` installed before this will work.

## Install

To get started, create a Python virtual environment in this directory (`web`) and install the dependencies:

```bash
$ python3 -m venv .venv

$ source .venv/bin/activate

$ pip3 install wheel

$ pip3 install -r requirements.txt
```

## Running

Use the `run_server.sh` script to run the web server:

```bash
$ ./run_server.sh
```

The web interface should now be accessible at [http://localhost:5000](http://localhost:5000).

Run `./run_server.sh --help` to see available options.
