"""Independent seeded gradient noise and warped fractal terrain."""

import hashlib
import math
import random

_GRADIENTS = ((1, 0), (-1, 0), (0, 1), (0, -1),
              (.7071067811865476, .7071067811865476),
              (-.7071067811865476, .7071067811865476),
              (.7071067811865476, -.7071067811865476),
              (-.7071067811865476, -.7071067811865476))


class _Noise:
    def __init__(self, seed):
        permutation = list(range(256))
        random.Random(seed).shuffle(permutation)
        self.permutation = tuple(permutation)*2

    def sample(self, x, y):
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('terrain coordinates overflow; increase terrain_scale')
        ix, iy = math.floor(x), math.floor(y)
        fx, fy = x-ix, y-iy
        u, v = fx**3*(fx*(fx*6-15)+10), fy**3*(fy*(fy*6-15)+10)
        dots = []
        for ox, oy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            index = self.permutation[self.permutation[(ix+ox)&255]+((iy+oy)&255)]&7
            gx, gy = _GRADIENTS[index]
            dots.append(gx*(fx-ox)+gy*(fy-oy))
        a = dots[0]+u*(dots[1]-dots[0])
        b = dots[2]+u*(dots[3]-dots[2])
        return a+v*(b-a)


class TerrainField:
    def __init__(self, seed: int, *, scale: float = 30, octaves: int = 5,
                 roughness: float = .45, warp_strength: float = .35):
        if type(seed) is not int:
            raise ValueError('terrain seed must be an integer')
        if (any(type(v) not in (int, float) or not math.isfinite(v)
                for v in (scale, roughness, warp_strength))
                or scale <= 0 or not 0 <= roughness <= 1 or not 0 <= warp_strength <= 1
                or type(octaves) is not int or not 1 <= octaves <= 8):
            raise ValueError('invalid terrain scale, octaves, roughness, or warp strength')
        self.scale, self.octaves = scale, octaves
        self.roughness, self.warp_strength = roughness, warp_strength
        def tagged(tag):
            return int.from_bytes(hashlib.sha256(f'{seed}:{tag}'.encode()).digest()[:8], 'big')
        self.base = _Noise(tagged('terrain'))
        self.warp_x, self.warp_y = _Noise(tagged('warp-x')), _Noise(tagged('warp-y'))

    def sample(self, x: float, y: float) -> float:
        x, y = x/self.scale, y/self.scale
        if self.warp_strength:
            wx, wy = self.warp_x.sample(x*.5, y*.5), self.warp_y.sample(x*.5, y*.5)
            x, y = x+self.warp_strength*wx, y+self.warp_strength*wy
        amplitude = 1.0
        total = weight = 0.0
        for _ in range(self.octaves):
            total += amplitude*self.base.sample(x, y)
            weight += amplitude
            amplitude *= self.roughness
            if amplitude == 0:
                break
            x, y = x*2, y*2
        return total/weight
