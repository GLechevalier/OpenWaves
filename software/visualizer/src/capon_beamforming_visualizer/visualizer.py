import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data'))

from data import capon4, capon5

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

# Vos données
data_bois = np.array(capon4).reshape((10, 32, 16))
data_cuivre = np.array(capon5).reshape((10, 32, 16))

# Création de la figure avec 2 subplots côte à côte
#fig, (ax2) = plt.subplots(1, 1, figsize=(8, 8))
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
plt.subplots_adjust(bottom=0.15, wspace=0.3)

# Trouver les limites globales pour une échelle commune (optionnel)
vmin_bois = data_bois.min()
vmin_cuivre = data_cuivre.min()
vmax_bois = data_bois.max()
vmax_cuivre = data_cuivre.max()

# Afficher les premières heatmaps
im1 = ax1.imshow(data_bois[0], cmap='hot', aspect='auto', interpolation='nearest', vmin=vmin_bois, vmax=vmax_bois)
im2 = ax2.imshow(data_cuivre[0], cmap='hot', aspect='auto', interpolation='nearest', vmin=vmin_cuivre, vmax=vmax_cuivre)

# Configuration des axes pour le bois
ax1.set_xlabel('Azimuth')
ax1.set_ylabel('Elevation')
ax1.set_title('Received heatmap - Image 0/9')

# Configuration des axes pour le cuivre
ax2.set_xlabel('Azimuth')
ax2.set_ylabel('Elevation')
ax2.set_title('Received heatmap - Image 0/9')

# Colorbars
cbar1 = plt.colorbar(im1, ax=ax1, label='Intensity')
cbar2 = plt.colorbar(im2, ax=ax2, label='Intensity')

# Créer le slider
ax_slider = plt.axes([0.2, 0.05, 0.6, 0.03])
slider = Slider(ax_slider, 'Image', 0, 8, valinit=0, valstep=1)

# Fonction de mise à jour
def update(val):
    idx = int(slider.val)
    
    # Mettre à jour les données des deux images
    im1.set_data(data_bois[idx])
    im2.set_data(data_cuivre[idx])
    
    # Mettre à jour les limites de la colorbar (échelle commune)
    im1.set_clim(vmin=vmin_bois, vmax=vmax_bois)
    im2.set_clim(vmin=vmin_cuivre, vmax=vmax_cuivre)
    
    # Mettre à jour les titres
    ax1.set_title(f'Received heatmap - Image {idx}/9')
    ax2.set_title(f'Received heatmap - Image {idx}/9')
    
    fig.canvas.draw_idle()

# Connecter le slider
slider.on_changed(update)

plt.show()