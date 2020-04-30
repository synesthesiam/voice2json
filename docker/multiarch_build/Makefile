.PHONY: amd64 armv6 armv7 arm64

all: amd64 armv7 arm64

amd64:
	docker build . -f Dockerfile.build.amd64 -t amd64/voice2json-build
	docker build . -f Dockerfile.run.amd64 -t amd64/voice2json-run
	docker build . -f Dockerfile.debian.amd64 -t amd64/voice2json-debian

armv6:
	docker build . -f Dockerfile.build.armv6 -t armv6/voice2json-build
	docker build . -f Dockerfile.run.armv6 -t armv6/voice2json-run
	docker build . -f Dockerfile.debian.armv6 -t armv6/voice2json-debian

armv7:
	docker build . -f Dockerfile.build.armv7 -t armv7/voice2json-build
	docker build . -f Dockerfile.run.armv7 -t armv7/voice2json-run
	docker build . -f Dockerfile.debian.armv7 -t armv7/voice2json-debian

armv64:
	docker build . -f Dockerfile.build.armv64 -t armv64/voice2json-build
	docker build . -f Dockerfile.run.armv64 -t armv64/voice2json-run
	docker build . -f Dockerfile.debian.arm64 -t arm64/voice2json-debian
