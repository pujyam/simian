for y in $(seq 1 100)
do
    #echo 1;
    #pypy ./mersenne_twister.py #luajit lcg_jit.lua;
    luajit lua_mod.lua
    #python ./mersenne_twister.py
done
