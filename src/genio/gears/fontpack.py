from pyxelxl import Font

from genio.base import asset_path


class FontPack:
    def __init__(self) -> None:
        self.retro = Font(asset_path("retro-pixel-petty-5h.ttf")).specialize(
            font_size=5
        )
        self.cute = Font(asset_path("retro-pixel-cute-prop.ttf")).specialize(
            font_size=11
        )
        self.arcade = Font(asset_path("retro-pixel-arcade.ttf")).specialize(font_size=8)
        self.capital_hill = Font(asset_path("Capital_Hill.ttf")).specialize(font_size=8)
        self.willow_branch = Font(asset_path("Willow_Branch.ttf")).specialize(
            font_size=8
        )
        self.noble_blabber = Font(asset_path("Noble_Blabber.ttf")).specialize(
            font_size=8
        )
        self.tomorrow_night = Font(asset_path("Tomorrow_Night.ttf")).specialize(
            font_size=8
        )


fonts = FontPack()
