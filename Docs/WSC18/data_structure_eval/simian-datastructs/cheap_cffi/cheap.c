#include <stdio.h>
#include <stdlib.h>
#include "cheap.h"
/* priority Queue implimentation via roman10.net */

void insert(struct heapNode aNode, struct heapNode* heap, int size) {
    int idx;
    struct heapNode tmp;
    idx = size + 1;
    heap[idx] = aNode;
    while (heap[idx].value < heap[idx/2].value && idx > 1) {
    tmp = heap[idx];
    heap[idx] = heap[idx/2];
    heap[idx/2] = tmp;
    idx /= 2;
    }
}

void shiftdown(struct heapNode* heap, int size, int idx) {
    int cidx;        //index for child
    struct heapNode tmp;
    for (;;) {
        cidx = idx*2;
        if (cidx > size) {
            break;   //it has no child
        }
        if (cidx < size) {
            if (heap[cidx].value > heap[cidx+1].value) {
                ++cidx;
            }
        }
        //swap if necessary
        if (heap[cidx].value < heap[idx].value) {
            tmp = heap[cidx];
            heap[cidx] = heap[idx];
            heap[idx] = tmp;
            idx = cidx;
        } else {
            break;
        }
    }
}

struct heapNode removeMin(struct heapNode* heap, int size) {
    int cidx;
    struct   heapNode rv = heap[1];
    //printf("%d:%d:%dn", size, heap[1].value, heap[size].value);
    heap[1] = heap[size];
    --size;
    shiftdown(heap, size, 1);
    return rv;
}

void enqueue(struct heapNode node, struct PQ *q) {
    insert(node, q->heap, q->size);
    ++q->size;
}

struct heapNode dequeue(struct PQ *q) {
  struct heapNode rv = removeMin(q->heap, q->size);
   --q->size;
   return rv; 
}

struct heapNode peak(struct PQ *q) {
  return q->heap[1];
}

void initQueue(struct PQ *q, int n) {
   q->size = 0;
   q->heap = (struct heapNode*)malloc(sizeof(struct heapNode)*(n+1));
}

int main(int argc, char **argv) {
    int n; 
    int i;
    struct PQ q;
    struct     heapNode hn;
    n = atoi(argv[1]);
    initQueue(&q, n);
    srand(time(NULL));
    for (i = 0; i < n; ++i) {
        hn.value = rand()%10000;
        printf("enqueue node with value: %dn", hn.value);
        enqueue(hn, &q);
    }
    printf("ndequeue all values:n");
    for (i = 0; i < n; ++i) {
        hn = dequeue(&q);
        printf("dequeued node with value: %d, queue size after removal: %dn", hn.value, q.size);
    }
}
