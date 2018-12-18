#include <stdio.h>

#include <stdlib.h>

/* priority Queue implimentation via roman10.net */

struct heapData {

    //everything from event
  //tx string
  char tx[64];
  //txID int
  int txID;
  //rx string
  char rx[64];
  //rxID int
  int rxID;
  //name string
  char name[64];
  //data Object
  char data[64];
  //time float
  float time;

  // optimistic (not supported)
  //antimessage boolean
  //gvt boolean
  //gvt value
  //color string

};

 

struct heapNode {

    int value;

    struct heapData data;               //dummy

};

 

struct PQ {

    struct heapNode* heap;

    int size;

};

 

void insert(struct heapNode aNode, struct heapNode* heap, int size) ;
void shiftdown(struct heapNode* heap, int size, int idx);
struct heapNode removeMin(struct heapNode* heap, int size);
void enqueue(struct heapNode node, struct PQ *q);
struct heapNode dequeue(struct PQ *q);
struct heapNode peak(struct PQ *q);
void initQueue(struct PQ *q, int n);
int nn = 1000000;
struct PQ q;
int main(int argc, char **argv);
