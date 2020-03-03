#include <time.h>
#include <stdlib.h>


void main(int argc, char ** argv){
  srand(1);   // should only be called once

  int i=0;
  int sum;
  for (i;i<1000000;i++){
    sum += rand();      // returns a pseudo-random integer between 0 and RAND_MAX
  }
}
