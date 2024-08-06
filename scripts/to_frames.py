import os
import sys

import webp


def main(image_file, output_pattern):
    # Load the webp animation
    imgs = webp.load_images(image_file, "RGB", fps=30)

    # Directory to save frames
    output_dir = os.path.dirname(output_pattern)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Save each frame as a PNG file
    for i, img in enumerate(imgs):
        filename = output_pattern % i
        img.save(filename)

    print(f'Successfully extracted {len(imgs)} frames to {output_dir or "."}')


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <image_file> <output_pattern>")
        print('Example: python script.py anim.webp "frames/frame%04d.png"')
        sys.exit(1)

    image_file = sys.argv[1]
    output_pattern = sys.argv[2]

    main(image_file, output_pattern)
