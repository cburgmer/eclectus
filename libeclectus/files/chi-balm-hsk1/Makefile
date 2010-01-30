installpath=/usr/local/share/eclectus/chi-balm-hsk1

SUBDIRS = 0 1 2 3 4 5 6 7 8 9 a b c d e f
FILES = index.tags.txt index.xml.bz2 package.xml

install:
	list='$(SUBDIRS)'; for subdir in $$list; do \
	  install -d $(installpath)/chi-balm-hsk1_ogg/$$subdir/ ; \
	  install -p -m 644 chi-balm-hsk1_ogg/$$subdir/* $(installpath)/chi-balm-hsk1_ogg/$$subdir/ ; \
	done;
	list='$(FILES)'; for file in $$list; do \
	  install -p -m 644 chi-balm-hsk1_ogg/$$file $(installpath)/chi-balm-hsk1_ogg/ ; \
	done;
	install -p -m 644 chi-balm-hsk1.db $(installpath)/
