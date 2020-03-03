def bsd_rand(seed):
   def rand():
      rand.seed = (1103515245*rand.seed + 12345) & 0x7fffffff
      return rand.seed
   rand.seed = seed
   return rand


def main():
   r = bsd_rand(1)
   #bsd_rand.rand()
   sum = 0
   for x in range(1000000):
      #sum += r()
      r()
   #pass


main()
