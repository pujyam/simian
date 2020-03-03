for y in $(seq 1 100)
do
    #echo 1;
    ./mt #luajit lcg_jit.lua;
done
