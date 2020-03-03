from cffi import FFI

ffibuilder = FFI()
with open('cheap.c', 'r') as fid:
    ffibuilder.set_source("_heap_i",
                          fid.read())
'''
ffibuilder.set_source("_heap_i",
                      r"""//passed to C compiler                                        
                      #include <stdio.h>                                                
                                                                                        
                      #include <stdlib.h>                                               
                      #include "cheap.h"                                                
        """,
                              libraries=[])
'''

    
ffibuilder.cdef("""
                struct heapData {
                      char tx[64];
                      int txID;
                      char rx[64];
                      int rxID;
                      char name[64];
                      float time;
                      char data[64];
                       ...;
                       };

                      struct heapNode {
                      int value;
                      struct heapData data;               //dummy
                       ...;};
 
                      struct PQ {                     
                      struct heapNode* heap;                    
                      int size;                      
                      ...;
                      } ;

                //void insert(struct heapNode aNode, struct heapNode* heap, int size) ;
                //void shiftdown(struct heapNode* heap, int size, int idx);
                //struct heapNode removeMin(struct heapNode* heap, int size);
                void enqueue(struct heapNode node, struct PQ *q);
                struct heapNode dequeue(struct PQ *q);
                struct heapNode peak(struct PQ *q);
                void initQueue(struct PQ *q, int n);
                //int nn = 1000000;
                //struct PQ q;
                //int main(int argc, char **argv);

""")

# 
#  Rank (Simian Engine) has a Bin heap 

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
