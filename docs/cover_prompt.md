# Prompt per cover del repository

Prompt pensato per generatori immagini AI (Midjourney, DALL-E, Stable Diffusion). Uso previsto: cover/social preview GitHub (1280x640px, ratio 2:1) o banner in cima al README.

## Prompt principale

```
Digital elevation model of a mountain valley rendered as a stylized 3D topographic
render, elevation color gradient from deep brown/tan peaks through green midlands
into blue flooded valley basin, glowing translucent blue floodwater spreading and
pooling in the lowest basin, subtle contour lines across the terrain, aerial
isometric perspective, dark navy background, clean scientific data-visualization
aesthetic, soft volumetric lighting on the water, minimal and elegant, high
detail terrain mesh, inspired by GIS hydrology and Plotly 3D surface plots,
no text, no logos, wide cinematic composition, 2:1 aspect ratio
```

## Varianti stile

- **Più tecnico/dashboard**: aggiungi `wireframe grid overlay, HUD-style annotations, cyan accent lines, dark mode UI aesthetic`
- **Più naturalistico**: aggiungi `photorealistic satellite imagery style, realistic terrain texture, natural lighting, golden hour`
- **Più astratto/minimal**: aggiungi `flat color bands, isometric low-poly terrain, generative art style, gradient mesh`

## Negative prompt (se supportato)

```
text, watermark, logo, people, buildings, cluttered, low detail, cartoonish, blurry
```

## Note

- Palette di riferimento: verde-marrone-bianco per la quota, blu semi-trasparente per l'acqua — stessa scala usata nelle mappe generate da `app/viz/raster_render.py` (vedi `docs/assets/ranking_map.png`), per coerenza visiva tra cover e screenshot nel README.
- Formato output consigliato: PNG, salvare come `docs/assets/cover.png` e referenziarlo in cima al README con `![cover](docs/assets/cover.png)`.
