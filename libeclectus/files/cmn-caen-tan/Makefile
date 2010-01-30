installpath=/usr/local/share/eclectus/cmn-caen-tan

SUBDIRS = 0 1 2 3 4 5 6 7 8 9 a b c d e f
FILES = index.tags.txt index.xml.bz2 package.xml

install:
	list='$(SUBDIRS)'; for subdir in $$list; do \
	  install -d $(installpath)/cmn-caen-tan_ogg/$$subdir/ ; \
	  install -p -m 644 cmn-caen-tan_ogg/$$subdir/* $(installpath)/cmn-caen-tan_ogg/$$subdir/ ; \
	done;
	list='$(FILES)'; for file in $$list; do \
	  install -p -m 644 cmn-caen-tan_ogg/$$file $(installpath)/cmn-caen-tan_ogg/ ; \
	done;
	install -p -m 644 cmn-caen-tan.db $(installpath)/
