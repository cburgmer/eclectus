all=chi-balm-hsk1 cmn-caen-tan bw.png bw.png.segment red.png order.gif

all: $(all)

alldist=chi-balm-hsk1-dist cmn-caen-tan-dist bw.png-dist bw.png.segment-dist red.png-dist order.gif-dist

commons: bw.png bw.png.segment red.png order.gif

chi-balm-hsk1: build/chi-balm-hsk1
cmn-caen-tan: build/cmn-caen-tan
bw.png: build/bw.png
bw.png.segment: build/bw.png.segment
red.png: build/red.png
order.gif: build/order.gif

build/chi-balm-hsk1_ogg.tar:
	mkdir -p build
	cd build && wget http://download.shtooka.net/chi-balm-hsk1_ogg.tar

build/cmn-caen-tan_ogg.tar:
	mkdir -p build
	cd build && wget http://download.shtooka.net/cmn-caen-tan_ogg.tar

build/chi-balm-hsk1: build/chi-balm-hsk1_ogg.tar
	mkdir -p build/chi-balm-hsk1
	cd build/chi-balm-hsk1 && tar -xf ../chi-balm-hsk1_ogg.tar
	cd ../../ && python -m libeclectus/buildtables -r build Pronunciation_zh_cmn --prefer=SwacChiBalmHsk1Builder --dataPath=libeclectus/files/build/chi-balm-hsk1 --database=sqlite:///libeclectus/files/build/chi-balm-hsk1/chi-balm-hsk1.db
	cp -u chi-balm-hsk1/* build/chi-balm-hsk1

build/cmn-caen-tan: build/cmn-caen-tan_ogg.tar
	mkdir -p build/cmn-caen-tan
	cd build/cmn-caen-tan && tar -xf ../cmn-caen-tan_ogg.tar
	cd ../../ && python -m libeclectus/buildtables -r build Pronunciation_zh_cmn --prefer=SwacCmnCaenTanBuilder --dataPath=libeclectus/files/build/cmn-caen-tan --database=sqlite:///libeclectus/files/build/cmn-caen-tan/cmn-caen-tan.db
	cp -u cmn-caen-tan/* build/cmn-caen-tan

build/bw.png:
	mkdir -p build/commons.tmp
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Bw.png stroke order images"
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Tbw.png stroke order images"
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Jbw.png stroke order images"
	mkdir -p build/bw.png
	mkdir -p build/bw.png/tbw.png
	mv build/commons.tmp/*-tbw.png build/bw.png/tbw.png
	mkdir -p build/bw.png/jbw.png
	mv build/commons.tmp/*-jbw.png build/bw.png/jbw.png
	mkdir -p build/bw.png/bw.png
	mv build/commons.tmp/*-bw.png build/bw.png/bw.png
	cp -u -p bw.png/* build/bw.png/
	cp COPYING.commons build/bw.png/COPYING

build/bw.png.segment: build/bw.png
	mkdir -p build/bw.png.segment/
	mkdir -p build/bw.png.segment/tbw.png.segment
	python ../scripts/segmenttiles.py --readfrom=bw.png.segment/tbw.png.segmentations -v --targetDir=build/bw.png.segment/tbw.png.segment build/bw.png/tbw.png/*-tbw.png
	mkdir -p build/bw.png.segment/jbw.png.segment
	python ../scripts/segmenttiles.py --readfrom=bw.png.segment/jbw.png.segmentations -v --targetDir=build/bw.png.segment/jbw.png.segment build/bw.png/jbw.png/*-jbw.png
	mkdir -p build/bw.png.segment/bw.png.segment
	python ../scripts/segmenttiles.py --readfrom=bw.png.segment/bw.png.segmentations -v --targetDir=build/bw.png.segment/bw.png.segment build/bw.png/bw.png/*-bw.png
	cp -u -p bw.png.segment/* build/bw.png.segment/
	cp COPYING.commons build/bw.png.segment/COPYING

build/red.png:
	mkdir -p build/commons.tmp
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Red.png stroke order images"
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Jred.png stroke order images"
#	cd build/commons.tmp && python ../../../scripts/downcommons.py "Tred.png stroke order images"
	mkdir -p build/red.png/
#	mkdir -p build/red.png/tred.png
#	mv build/commons.tmp/*-tred.png build/red.png/tred.png
	mkdir -p build/red.png/jred.png
	mv build/commons.tmp/*-jred.png build/red.png/jred.png
	mkdir -p build/red.png/red.png
	mv build/commons.tmp/*-red.png build/red.png/red.png
	cp -u -p red.png/* build/red.png/
	cp COPYING.commons build/red.png/COPYING

build/order.gif:
	mkdir -p build/commons.tmp
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Order.gif stroke order images"
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Jorder.gif stroke order images"
	cd build/commons.tmp && python ../../../scripts/downcommons.py "Torder.gif stroke order images"
	mkdir -p build/order.gif/
	mkdir -p build/order.gif/torder.gif
	mv build/commons.tmp/*-torder.gif build/order.gif/torder.gif
	mkdir -p build/order.gif/jorder.gif
	mv build/commons.tmp/*-jorder.gif build/order.gif/jorder.gif
	mkdir -p build/order.gif/order.gif
	mv build/commons.tmp/*-order.gif build/order.gif/order.gif
	cp -u -p order.gif/* build/order.gif/
	cp COPYING.commons build/order.gif/COPYING

# prepare .tar.gz
dist: $(alldist)

$(alldist): $(all)
	model=$(subst -dist,,$@); \
	version=`cd ../../ && python -c "import libeclectus; print libeclectus.__version__"`; \
	mkdir -p dist; \
	rm -rf dist/$$model; \
	cp -R build/$$model dist/$$model-$$version; \
	(cd dist/; rm $$model-$$version.tar.gz; tar -cf $$model-$$version.tar $$model-$$version; gzip $$model-$$version.tar) ; \
	rm -rf dist/$$model-$$version

.PHONY: clean cleanTmp
clean: cleanTmp
	rm -rf build/chi-balm-hsk1
	rm -rf build/cmn-caen-tan
	rm -rf build/bw.png
	rm -rf build/bw.png.segment
	rm -rf build/red.png
	rm -rf build/order.gif
	rmdir build

cleanTmp:
	rm -rf build/commons.tmp
	rm -rf build/chi-balm-hsk1_ogg.tar
	rm -rf build/cmn-caen-tan_ogg.tar
