									
/*****Please include following header files*****/
#include <stdint.h>
/***********************************************/

#define N (624)
#define M (397)
#define K (0x9908B0DFU)
#define HighestBit(u) ((u) & 0x80000000U)
#define LowestBit(u) ((u) & 0x00000001U)
#define LowestBits(u) ((u) & 0x7FFFFFFFU)
#define MixBits(u, v) (HighestBit(u)|LowestBits(v))

static uint32_t state[N + 1];
static uint32_t *nextRand;
static int left = -1;

void Seed(uint32_t seed)
{
	register uint32_t x = (seed | 1U) & 0xFFFFFFFFU;
	register uint32_t *s = state;
	register int j;

	for (left = 0, *s++ = x, j = N; --j; *s++ = (x *= 69069U) & 0xFFFFFFFFU);
}

uint32_t Reload()
{
	register uint32_t *p0 = state;
	register uint32_t *p2 = state + 2;
	register uint32_t *pM = state + M;
	register uint32_t s0;
	register uint32_t s1;
	register int j;

	if (left < -1) {
		Seed(4357U);
	}

	left = N - 1;
	nextRand = state + 1;

	for (s0 = state[0], s1 = state[1], j = N - M + 1; --j; s0 = s1, s1 = *p2++) {
		*p0++ = *pM++ ^ (MixBits(s0, s1) >> 1) ^ (LowestBit(s1) ? K : 0U);
	}

	for (pM = state, j = M; --j; s0 = s1, s1 = *p2++) {
		*p0++ = *pM++ ^ (MixBits(s0, s1) >> 1) ^ (LowestBit(s1) ? K : 0U);
	}

	s1 = state[0];
	*p0 = *pM ^ (MixBits(s0, s1) >> 1) ^ (LowestBit(s1) ? K : 0U);
	s1 ^= (s1 >> 11);
	s1 ^= (s1 << 7) & 0x9D2C5680U;
	s1 ^= (s1 << 15) & 0xEFC60000U;

	return (s1 ^ (s1 >> 18));
}


uint32_t Random()
{
	uint32_t y;

	if (--left < 0) {
		return Reload();
	}

	y = *nextRand++;
	y ^= (y >> 11);
	y ^= (y << 7) & 0x9D2C5680U;
	y ^= (y << 15) & 0xEFC60000U;

	return (y ^ (y >> 18));
}

								

void main(int argc, char** argv) {

  Seed(1);
  uint32_t sum = 0;
  int i=0;
  for (i;i<1000000;i++){
    sum += Random();
  }
  
}
