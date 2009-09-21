#!/bin/bash
#
# update .po files and compile .mo files
# 21.09.2009 cburgmer@ira.uka.de, taken from the anki project

if [ ! -d "libeclectus" ]
then
    echo "Please run this from the eclectus project directory"
    exit
fi

if [ ! -d "po" ]
then
    echo "Please run 'bzr clone lp:eclectus po' first"
    exit
fi

fileList=i18n.files
echo "Generating translations"

for dir in libeclectus
do
    echo "module $dir"
    for i in $dir/*.py
    do
        echo $i >> $dir/$fileList
    done

    version=$(python -c "import $dir; print $dir.__version__")
    potFile=po/$dir/messages.pot
    xgettext -s --no-wrap --package-name="$dir" --package-version=$version \
        --files-from=$dir/$fileList --output=$potFile
    for file in po/$dir/*.po
    do
        echo -n $file
        msgmerge -s --no-wrap $file $potFile > $file.new && mv $file.new $file
        outdir=$(echo $file | \
            perl -pe 's%po/(.*)/(.*)\.po%\1/locale/\2/LC_MESSAGES%')
        mkdir -p $outdir
        outfile="$outdir/$dir.mo"
        msgfmt $file --output-file=$outfile
    done
    rm $dir/$fileList
done
