Pen Apple
=============

A roguelike deckbuilder, code-name `genio`.

## Setting Up

We tested with Python 3.10.12 (but any Python above 3.10) should work. Our testing was done on an Apple M1 MacBook Pro, but nothing in the code should be platform-specific. Remember to install SDL2 `sudo apt-get install -y libsdl2-2.0-0` if on Ubuntu, possibly also required on macOS if SDL is reported to be missing.

We use [Just](https://github.com/casey/just) as our command runner, and [Poetry](https://python-poetry.org/) to manage dependencies. Install both for the smoothest experience.

To install Python dependencies:

```bash
poetry install
```

Checkout commit `4f24a925844396d175e5ca3e80d8954351a493cc` if you want to see the code at the end of the competition.

## Running the Game

Ensure `GOOGLE_API_KEY` is in your environment variables, or else Gemini will not work.

```bash
just play # Run the main scene, where you play cards and fight enemies.
```

Others scenes to run:

 - `poetry run python -m genio.main --module genio.scene_stages` to run the stage selection scene
 - `poetry run python -m genio.main --module genio.scene_booster` to run the booster pack / stage results scene
 - `poetry run python -m genio.main --module genio.scene_intro` to run the "explanation" or intro scene

To add/test new cards, the simplest way is to modify `strings.toml` inside `assets`.

```toml
# The initial deck. As stated in the video, this *is* the entire definition of the cards. Not pre-programmed logic is needed.
[initial_deck]

cards = [
    "left * 3",
    "right * 3",
    "Smash * 1 # Deal 1 damage and apply vulnerable for 2 turn.",
    "Slash * 4 # Deal 2 damage to a target.",
    "Block * 3 # Gain 1 shield point.",
    "4 of Spades * 2",
]
```

## Licenses of the other projects

See the `LICENSE` file for the license of this project. We additionally used MIT-licensed code from other projects.

 1. [Pyxel](https://github.com/kitao/pyxel)
 2. [Parse](https://github.com/r1chardj0n3s/parse)
 3. [Pico-ps](https://github.com/MaxwellDexter/pico-ps)

There `LICENSE` files are included below, in no particular order:

<details>
<summary>Pyxel</summary>
<pre>
MIT License

Copyright (c) 2018 Takashi Kitao

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
</pre>
</details>

<details>
<summary>parse</summary>
<pre>
Copyright (c) 2012-2019 Richard Jones <richard@python.org>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
</pre>
</details>


<details>
<summary>pico-ps</summary>
<pre>
MIT License

Copyright (c) 2020 MaxwellDexter

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
</pre>
</details>


## Related Projects

Much support code specifically done for this game is in other projects.

 1. https://github.com/RuneBlaze/marble-noise -- Rust code of how the noise background is generated
 2. https://github.com/RuneBlaze/pyxelxl -- Rust + Python library of drawing TTF, rotating sprites in Pyxel

## Contact Information

If you encounter any issues or have questions, feel free to file an issue here. I check my GitHub (nearly) every day.