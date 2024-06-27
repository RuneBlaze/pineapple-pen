import numpy as np


def fix_palette(quantized_image):
    correct_mapping = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 11, 12, 14, 15]
    inverse = np.argsort(correct_mapping)

    # Create a new array with corrected indices
    corrected_quantized_image = np.zeros_like(quantized_image)

    for i in range(len(inverse)):
        corrected_quantized_image[quantized_image == i] = inverse[i]

    return corrected_quantized_image


broken = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 11, 12, 14, 15])
print(fix_palette(broken))
