chi-balm-hsk1_ogg:
	wget http://download.shtooka.net/chi-balm-hsk1_ogg.tar
	tar -xf chi-balm-hsk1_ogg.tar
	../buildtables.py -rb Pronunciation_zh_cmn

bw.png:
	mkdir -p commons.tmp
	cd commons.tmp && python ../../scripts/downcommons.py "Bw.png stroke order images"
	cd commons.tmp && python ../../scripts/downcommons.py "Tbw.png stroke order images"
	cd commons.tmp && python ../../scripts/downcommons.py "Jbw.png stroke order images"
	mkdir -p tbw.png
	mv commons.tmp/?-tbw.png tbw.png
	mkdir -p jbw.png
	mv commons.tmp/?-jbw.png jbw.png
	mkdir -p bw.png
	mv commons.tmp/?-bw.png bw.png

bw.png.segment: bw.png
	python ../scripts/segmenttiles.py --readfrom=../data/tbw.png.segmentations -v tbw.png/?-tbw.png
	mkdir -p tbw.png.segment
	mv tbw.png/?-tbw.*.png tbw.png.segment
	python ../scripts/segmenttiles.py --readfrom=../data/jbw.png.segmentations -v jbw.png/?-jbw.png
	mkdir -p jbw.png.segment
	mv jbw.png/?-jbw.*.png jbw.png.segment
	python ../scripts/segmenttiles.py --readfrom=../data/bw.png.segmentations -v bw.png/?-bw.png
	mkdir -p bw.png.segment
	mv bw.png/?-bw.*.png bw.png.segment

red.png:
	cd commons.tmp && python ../../scripts/downcommons.py "Red.png stroke order images"
	cd commons.tmp && python ../../scripts/downcommons.py "Jred.png stroke order images"
#	cd commons.tmp && python ../../scripts/downcommons.py "Tred.png stroke order images"
#	mkdir -p tred.png
#	mv commons.tmp/?-tred.png tred.png
	mkdir -p jred.png
	mkdir -p red.png
	mv commons.tmp/?-red.png red.png

order.gif:
	mkdir -p commons.tmp
	cd commons.tmp && python ../../scripts/downcommons.py "Order.gif stroke order images"
	cd commons.tmp && python ../../scripts/downcommons.py "Jorder.gif stroke order images"
	cd commons.tmp && python ../../scripts/downcommons.py "Torder.gif stroke order images"
	mkdir -p torder.gif
	mv commons.tmp/?-torder.gif torder.gif
	mkdir -p jorder.gif
	mv commons.tmp/?-jorder.gif jorder.gif
	mkdir -p order.gif
	mv commons.tmp/?-order.gif order.gif

commons: bw.png bw.png.segment red.png order.gif

all: commons chi-balm-hsk1_ogg

clean: cleanTmp
	rm -rf chi-balm-hsk1_ogg
	rm -rf bw.png jbw.png tbw.png
	rm -rf bw.png.segment jbw.png.segment tbw.png.segment
	rm -rf red.png jred.png tred.png
	rm -rf order.gif jorder.gif torder.gif

cleanTmp:
	rm -f chi-balm-hsk1_ogg.tar
	rm -rf commons.tmp

cleanSegmentTmp:
	rm -rf bw.png jbw.png tbw.png
