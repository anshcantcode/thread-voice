# Restored frontend and asset provenance

The original THREAD visual identity was restored in v0.1.1 at the project owner's request. It comes from [thread-team-guide at 2ec4ecc](https://github.com/anshcantcode/thread-team-guide/tree/2ec4eccf3dd2b5568814fc2033c4bc353008bff2), the ReflexAi team's earlier THREAD project. Retain this attribution when redistributing the inherited frontend.

| Files under `src/thread_voice/web/` | Origin |
|---|---|
| `style.css`, `workspace.css`, `galaxy.css` | Original THREAD design system and acoustic-blue theme |
| `orb.js` | Original live WebGL orb renderer, with Canvas2D fallback and reduced-motion handling |
| `images/thread-sphere.png` | Earlier project's generated acoustic-sphere artwork, retained for the renderer's fallback |
| `fonts/Manrope.ttf`, `fonts/Newsreader.ttf` | Bundled Google Fonts; SIL Open Font License notices are included next to both font files |
| `fonts/sources.json` | Original font source and checksum manifest |

The HTML layout and icon paths restore the earlier interface's structure and appearance, adapted to the new runtime's actual capabilities. New integration code and the Python runtime are covered by this repository's MIT license. The font licenses and inherited asset provenance remain separate. Third-party marks do not imply endorsement.
