import io
import matplotlib.pyplot as plt
import numpy as np

def generate_heatmap(ndvi_array: np.ndarray, colormap: str = "RdYlGn") -> bytes:

    # Setup my figure without axes/margnins for a clean image output
    fig, ax = plt.subplots(figsize=(8,8))
    fig.patch.set_visible(False)
    ax.axis("off")

    print(ndvi_array)

    # Render ndvi array using colormap
    heatmap = ax.imshow(ndvi_array, cmap=colormap, vmin=-0.2, vmax=1.0)

    # Add a colorbar legend
    cbar = fig.colorbar(heatmap, ax=ax, fraction=0.045, pad = 0.04)
    cbar.set_label("NDVI Index", rotation=270, labelpad=15)
    cbar.set_ticks([0.0, 0.2, 0.5, 0.8, 1.0])

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    buffer.seek(0)

    return buffer.getvalue()
