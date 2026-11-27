/*
 *  Copyright (C) 2011-2016  OpenDungeons Team
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef GOLDHEAPLAYOUT_H
#define GOLDHEAPLAYOUT_H

//! \brief Where the coins of our gold heap model lie, taken from the model itself (our own asset). The coins are in
//! an order in which any first part of the list is spread over the whole heap.
namespace GoldHeapLayout
{
//! One coin: place inside the round foot of the heap (-1..1) and how its face leans (x, y of its normal)
struct Coin
{
    float mX;
    float mY;
    float mLeanX;
    float mLeanY;
};

static const int coinCount = 50;
static const Coin coins[coinCount] =
{
    {0.019f, -0.053f, 0.085f, -0.072f},
    {0.438f, 0.899f, 0.136f, 0.227f},
    {-0.836f, 0.423f, -0.279f, 0.070f},
    {-0.422f, -0.903f, -0.183f, -0.216f},
    {0.902f, -0.321f, 0.493f, 0.005f},
    {0.318f, -0.787f, 0.257f, -0.094f},
    {-0.916f, -0.296f, -0.251f, -0.074f},
    {-0.251f, 0.886f, -0.054f, 0.315f},
    {0.913f, 0.273f, 0.246f, 0.076f},
    {-0.449f, 0.156f, -0.291f, 0.099f},
    {0.167f, 0.381f, 0.115f, 0.163f},
    {-0.300f, -0.479f, -0.045f, -0.303f},
    {0.552f, 0.479f, 0.005f, 0.029f},
    {0.647f, -0.012f, 0.210f, 0.089f},
    {-0.197f, 0.525f, 0.005f, 0.080f},
    {0.149f, -0.486f, 0.105f, -0.139f},
    {-0.542f, 0.592f, -0.275f, 0.173f},
    {0.146f, 0.750f, 0.103f, 0.453f},
    {0.557f, -0.578f, 0.255f, -0.182f},
    {-0.600f, -0.099f, -0.360f, 0.031f},
    {-0.581f, -0.401f, -0.208f, 0.015f},
    {0.393f, -0.115f, 0.214f, 0.164f},
    {-0.135f, -0.691f, -0.077f, -0.137f},
    {-0.133f, -0.242f, -0.200f, -0.083f},
    {0.195f, 0.144f, 0.027f, -0.080f},
    {-0.318f, -0.036f, -0.361f, 0.072f},
    {-0.219f, 0.170f, -0.153f, 0.086f},
    {-0.006f, 0.240f, 0.033f, 0.011f},
    {-0.721f, 0.079f, -0.276f, 0.048f},
    {0.604f, -0.213f, 0.123f, 0.064f},
    {-0.479f, 0.402f, -0.229f, 0.106f},
    {0.201f, -0.122f, 0.133f, -0.081f},
    {0.408f, -0.473f, 0.041f, -0.036f},
    {0.406f, 0.544f, 0.268f, 0.507f},
    {0.002f, -0.438f, 0.111f, -0.173f},
    {-0.135f, -0.093f, -0.090f, -0.066f},
    {-0.048f, 0.357f, -0.051f, 0.366f},
    {-0.636f, 0.161f, -0.087f, -0.004f},
    {0.181f, 0.258f, 0.088f, -0.023f},
    {0.207f, -0.788f, 0.009f, -0.071f},
    {0.599f, 0.058f, 0.411f, -0.103f},
    {0.225f, -0.496f, 0.019f, -0.138f},
    {-0.280f, 0.129f, 0.027f, 0.055f},
    {-0.194f, -0.265f, -0.077f, -0.075f},
    {-0.215f, 0.586f, -0.243f, 0.335f},
    {0.139f, -0.133f, 0.092f, 0.009f},
    {0.562f, 0.528f, 0.284f, 0.141f},
    {-0.536f, -0.421f, -0.028f, 0.003f},
    {0.195f, 0.215f, 0.247f, 0.326f},
    {-0.187f, 0.544f, -0.208f, 0.214f}
};
}

#endif // GOLDHEAPLAYOUT_H
