# Asset provenance — v1.2.0

PDF assets are served locally from `frontend/public/vendor`, with their licence
files beside them. No runtime CDN request is needed to prepare a report.

| Asset | Source and licence |
| --- | --- |
| jspdf.umd.min.js | jsPDF v4.2.1, MIT. Exact official file at commit `4562ce8aa35bd5ecd98cd5e262e3da2af96476f6`, repository `parallax/jsPDF`, `dist/jspdf.umd.min.js`. Local bytes verified against official Git blob SHA `0e600d49d2b2bf81dd97c1509e22d108c2ddd3b4`. |
| BloomSans.ttf | DejaVu Sans 2.37, from the installed DejaVu font package. Unmodified TTF bytes under a local serving filename. Redistribution terms and notices in BloomSans.LICENSE. |
| NotoNaskhArabic-Regular.ttf | Google Fonts `ofl/notonaskharabic/NotoNaskhArabic[wght].ttf`, SIL OFL 1.1. Unmodified variable TTF with default weight 400, served under the local filename shown. Exact Git blob SHA `a8d2867262dc7bb28492ad746de5d56235735c8b`; includes Latin and Urdu presentation glyphs. |

Sources:

- [Pinned jsPDF source](https://github.com/parallax/jsPDF/blob/4562ce8aa35bd5ecd98cd5e262e3da2af96476f6/dist/jspdf.umd.min.js)
- [Noto Naskh source file](https://github.com/google/fonts/blob/main/ofl/notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf) (the Git blob SHA above identifies the exact downloaded bytes)
- [Noto Naskh licence](https://github.com/google/fonts/blob/main/ofl/notonaskharabic/OFL.txt)
- [DejaVu project](https://dejavu-fonts.github.io/)

SHA-256 checksums of the shipped font/runtime files:

```text
e6551fcdc32f09d6853b2c5126d18d01d9447e0da618a41a11ebeee0f6c20d54  jspdf.umd.min.js
ae7b7855e115a5966d8b1b3f80f254ccc117ec86f9965e202ee2940453837280  BloomSans.ttf
67b5a525a661b607971fbd3f96a81b89d3a768e74534fca84f18ac97e6fab72f  NotoNaskhArabic-Regular.ttf
```

The original PE forest provenance, inputs, original pickle digest and evaluation
limitations remain documented in PE-MODEL.md and the packaged legacy
model manifest. v0.9.0 adds checked fitted node weights for actual TreeSHAP:

```text
c81f12c94041328ac21bcc1b054087ae5e1cc54b8b8d78ece665fcecfd554d3c  explanation-weights.json
```

The offline exporter loads only the matching original pickle for maintainers.
That pickle is not included or loaded by the web application.


## Interface references and original artwork (1.2.0)

Public official product pages reviewed on 21 October 2026:

| Product | Design idea applied to BloomCare | Official reference |
| --- | --- | --- |
| Flo pregnancy tracker | Give pregnancy progress a clear place in the patient overview, with a readable next step. | [Flo](https://flo.health/product-tour/pregnancy-app) |
| Philips Pregnancy+ | Organize the pregnancy journey and supporting tools with a clear visual hierarchy. | [Pregnancy+](https://philips-digital.com/pregnancy-new/) |
| Maven maternity care | Keep access to a care professional and the next consultation easy to find. | [Maven](https://www.mavenclinic.com/programs/maternity-and-newborn-care) |

These are layout/interaction references. No competitor logo, illustration, photograph, interface screenshot, testimonial, statistic or clinical outcome claim is copied into BloomCare. The maternal-embrace SVG mark in `frontend/public/bloomcare-mark.svg` and the SVG illustration in `frontend/src/ui.jsx` are original project artwork. BloomCare does not imply affiliation with these products.
