# SHOPY — Rendre le design « non reconnaissable comme fait par une IA »

> Objectif : enlever les marqueurs visuels qui font dire « ça, c'est fait avec l'IA »
> ✅ **Chantier 1 TERMINÉ** (20/09/2026) : ~65 emojis UI -> Bootstrap Icons 1.11.3 dans _vendor_header, _client_header, dashboard_vendeur, espace_client, catalogue. Exceptions: cat.icone (BDD), emojis marketing. Templates OK, check OK.
>
> sans casser l'identité SHOPY (marketplace guinéenne, mobile-first, dark).

---

## 1. Diagnostic : ce qui « trahit » l'IA aujourd'hui dans SHOPY

J'ai audité les fichiers réels du projet. Les 10 marqueurs trouvés :

| # | Marqueur « généré par IA » | Où c'est dans ton code |
|---|----------------------------|------------------------|
| 1 | **Emojis utilisés comme icônes d'UI** (💰 📷 📍 ✅ 🔔 📖 ⚙️ 🛒 🏪) | `_vendor_header.html`, `_client_header.html`, `catalogue.html`, `dashboard_vendeur.html` |
| 2 | **Police Inter partout** — c'est LA police par défaut de tous les templates IA | `static/core/css/global.css`, `welcome.css` |
| 3 | **Dégradés parfaits à 135°, deux tons, très lisses** | `_vendor_header.html`, `_client_header.html`, `loyalty-consent-panel` (`#172554 → #0f766e`) |
| 4 | **Glassmorphism** (`backdrop-filter: blur(18px)` + `rgba(255,255,255,.08)`) | `_client_header.html` (`.glass-card`) |
| 5 | **Tout est arrondi à l'excès** : `border-radius: 20px`, `999px`, `16px` partout | quasi tous les templates |
| 6 | **Palette dark « GitHub » générique** : `#0d1117`, `#161b22`, `#238636`, `#388bfd`, `#3b82f6` | `global.css`, headers, `evaluer_produit.html` |
| 7 | **Orbes flous animés en arrière-plan** (blur + float 8s infinite) | `_client_header.html` → **déjà supprimé** ✅ |
| 8 | **Animations uniformes** : `transition: all .3s ease` sur tout, pulse infini | `_client_header.html`, `welcome.html` (`flashPulse`), `evaluer_produit.html` |
| 9 | **Badges pastel arrondis** systématiques (« ✓ Programme activé », « ✅ Client vérifié ») | `dashboard_vendeur.html`, headers |
| 10 | **Ombres douces identiques** (`0 14px 28px rgba(0,0,0,.22)`) sur chaque carte | headers, cartes produit |

**Conclusion du diagnostic** : le problème n'est pas « c'est moche », c'est **l'uniformité**.
Une IA applique le même traitement (même rayon, même ombre, même durée d'animation, même
palette, mêmes emojis) partout. Un designer humain, lui, **hiérarchise** : il casse
volontairement l'uniformité à certains endroits et pas à d'autres.

---


## 2. Les 7 chantiers à mener (du plus rentable au moins rentable)

### Chantier 1 — Remplacer les emojis-icônes par de vraies icônes (impact : ★★★★★)

C'est **le** marqueur n°1. Tu as déjà **Bootstrap Icons** dans le projet
(`bottom_nav.html` utilise `<i class="bi bi-shop">`) : exploite-le partout.

```html
<!-- Avant (marqueur IA) -->
<span class="dashboard-stat-icon">💰</span>

<!-- Après (pro) -->
<i class="bi bi-cash-stack dashboard-stat-icon" aria-hidden="true"></i>
```

Correspondances à appliquer :

| Emoji | Remplacer par |
|-------|---------------|
| 💰 ventes | `bi-cash-stack` |
| 📷 photo | `bi-camera` |
| 📍 ville | `bi-geo-alt` |
| ✅ vérifié | `bi-patch-check-fill` |
| 🔔 commandes | `bi-bell` |
| 📖 guide | `bi-book` |
| ⚙️ réglages | `bi-sliders` / `bi-gear` |
| 🏪 boutique | `bi-shop` |
| 👋 salutation | *à supprimer* (un humain n'écrit pas « Bonjour 👋 » en prod) |

Fichiers concernés : `_vendor_header.html`, `_client_header.html`,
`dashboard_vendeur.html`, `commandes_vendeur.html`, `catalogue.html`,
`espace_client.html`, `parametres_*.html`.

> ⚠️ Garde les emojis **uniquement dans les messages marketing** (annonces, promos),
> jamais dans la navigation ni les en-têtes.

---

### Chantier 2 — Sortir de la police Inter (impact : ★★★★☆)

Inter + system-ui = signature typique des générateurs. Trois pistes, du plus simple au plus marqué :

1. **Simple et sûr** : passer sur une paire neutre mais moins banale :
   `Manrope` (titres) + `IBM Plex Sans` (texte). Auto-hébergées, pas de Google Fonts.
2. **Marqué** : titres en `Fraunces` ou `Bricolage Grotesque` (caractère très « humain »),
   texte en `Inter Tight`.
3. **Très typé SHOPY** : garder une sans haute lisibilité pour le corps, mais donner
   aux **prix** et aux **chiffres de ventes** une police tabulaire (`font-variant-numeric: tabular-nums`)
   + un poids 800. Les prix deviennent une signature visuelle forte.

```css
/* static/core/css/global.css */
:root {
  --shopy-font-display: 'Manrope', 'Segoe UI', sans-serif;
  --shopy-font-body: 'IBM Plex Sans', 'Segoe UI', sans-serif;
  --shopy-font-num: 'IBM Plex Mono', monospace;
}
body { font-family: var(--shopy-font-body); }
h1, h2, h3 { font-family: var(--shopy-font-display); }
.price, .dashboard-stat-value {
  font-family: var(--shopy-font-num);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
```

---

### Chantier 3 — Créer une vraie palette SHOPY (impact : ★★★★☆)

Aujourd'hui ta palette est un copier-coller de GitHub dark.
Construis une palette **propre à SHOPY** (inspiration Guinée : vert forêt profond,
or/sable chaud, terre de bauxite), avec **3 teintes max** + neutres.

```css
/* static/core/css/global.css */
:root {
  /* Identité */
  --shopy-forest:   #0F3D2E;   /* vert forêt profond (confiance, Afrique) */
  --shopy-leaf:     #1E7A54;   /* vert action / CTA */
  --shopy-gold:     #E0A526;   /* or / accent chaud (promos, prix) */
  --shopy-clay:     #B4552D;   /* terre cuite (alertes, refus) */

  /* Neutres chauds — remplace le bleu-gris GitHub */
  --shopy-bg:       #12100E;
  --shopy-surface:  #1B1815;
  --shopy-border:   #2B2723;
  --shopy-text:     #F2EDE7;
  --shopy-muted:    #A79E93;
}
```

**Règle d'or** : supprime le bleu `#388bfd` / `#3b82f6` de l'interface.
C'est précisément la couleur « défaut IA ». Remplace-le par `--shopy-gold` (accents)
et `--shopy-leaf` (actions).

---

### Chantier 4 — Casser l'uniformité des rayons et des ombres (impact : ★★★★☆)

Au lieu de `border-radius: 20px` partout, définis **une échelle** et utilise-la
de façon **irrégulière et intentionnelle** :

```css
:root {
  --r-xs: 6px;    /* badges, tags */
  --r-sm: 10px;   /* inputs, boutons */
  --r-md: 16px;   /* cartes produit */
  --r-lg: 24px;   /* modales, panneaux */
}
```

Et surtout : **une seule ombre par niveau**, plus douce et **teintée** (jamais du noir pur) :

```css
/* Avant : ombre identique partout, noire (marqueur IA) */
box-shadow: 0 14px 28px rgba(0,0,0,.22);

/* Après : ombre teintée + réservée aux éléments prioritaires */
--shadow-card:  0 2px 6px rgba(15,61,46,.35);    /* cartes au repos */
--shadow-float: 0 12px 24px rgba(0,0,0,.45);     /* seulement modales / menus */
```

---

### Chantier 5 — Remplacer le glassmorphism par de la matière (impact : ★★★☆☆)

`backdrop-filter: blur(18px)` sur fond semi-transparent est un marqueur très « 2024-IA ».
Remplace-le par un **fond opaque + bordure lumineuse en haut** (technique
« inner highlight »), qui donne la même profondeur sans l'effet « verre » :

```css
.glass-card {
  background: var(--shopy-surface);
  border: 1px solid var(--shopy-border);
  border-top-color: rgba(255,255,255,.10);   /* lumière venant du haut */
  box-shadow: var(--shadow-card);
}
```

---

### Chantier 6 — Rendre les animations « physiques » (impact : ★★★☆☆)

Aujourd'hui : `transition: all .3s ease` partout — durée et courbe identiques = signature IA.

```css
:root {
  --ease-out: cubic-bezier(.2, .8, .3, 1);
  --t-fast: 120ms;
  --t-base: 200ms;
}
```

Règles :
- `transition: all` → **cibler la propriété** (`background-color`, `transform`).
- Durées **courtes** (120–200 ms). Les animations longues (`8s infinite`) → **supprimer**.
- **Une seule** animation d'accent dans toute l'app : un léger `scale(0.97)` au tap.
  C'est ce retour « haptique visuel » qui distingue une app native soignée d'un template.

```css
.SHOPY-nav-item:active, .login-button:active, .loyalty-activate-btn:active {
  transform: scale(0.97);
  transition: transform var(--t-fast) var(--ease-out);
}
```

---

### Chantier 7 — Les détails qui font « fait à la main » (impact : ★★★☆☆)

Ce sont ces micro-choix qu'aucune IA ne fait spontanément :

1. **États vides rédigés** avec une vraie voix SHOPY, pas « Aucun produit trouvé ».
2. **Bordures asymétriques** : `border-left: 3px solid var(--shopy-gold)` sur les cartes
   promo et les commandes en attente → repère visuel métier, pas décoratif.
3. **Densité variable** : les écrans « consultation » (catalogue) respirent
   (`padding: 20px`), les écrans « action » (commandes vendeur) sont **denses**
   (`padding: 12px`). Une IA met exactement le même padding partout.
4. **Images produits assombries au survol** (`filter: brightness(.75)`) avec le prix
   qui remonte : rendu « e-commerce réel », pas « grille de démo ».
5. **Squelettes de chargement** (`skeleton`) au lieu de spinners génériques.
6. **Écran de démarrage sobre** (logo SHOPY) au premier chargement, comme les vraies apps.
7. **Orthotypographie FR** : espace insécable avant `: ; ! ?`, `250 000 GNF` avec espace
   fine insécable. Ce niveau de finition est très rare et se remarque immédiatement.

---


## 3. Plan d'action conseillé (3 vagues)

### Vague 1 — « effets immédiats » (1 à 2 jours)
- Chantier 1 : emojis → Bootstrap Icons (tous les en-têtes et la nav)
- Chantier 3 : palette SHOPY + **suppression du bleu `#388bfd` / `#3b82f6`**
- Chantier 6 : durées d'animation courtes + `transition` ciblée
→ **Déjà en partie fait** : orbes néon retirés, ombres « double halo » supprimées,
`transition: all 3s` remplacés dans les en-têtes (`_client_header.html`, `_vendor_header.html`).

### Vague 2 — « personnalité » (3 à 5 jours)
- Chantier 2 : nouvelle paire typographique + chiffres tabulaires pour les prix
- Chantier 4 : échelle de rayons + ombres teintées
- Chantier 5 : fin du glassmorphism

### Vague 3 — « finition artisanale » (1 semaine)
- Chantier 7 : états vides rédigés, densité variable, squelettes, orthotypographie FR
- Écran de démarrage + micro-interactions au tap

---

## 4. Les 5 règles à retenir

1. **Une seule couleur d'accent.** Si tout est accentué, rien ne l'est.
2. **Pas d'emoji dans l'UI.** Les emojis sont réservés aux textes marketing.
3. **Jamais `transition: all`.** Cible la propriété, garde 120–200 ms.
4. **Casse l'uniformité volontairement** : rayons, densité, ombres varient selon l'usage.
5. **Le détail qui tue** : espaces insécables FR + chiffres tabulaires sur les prix.

---

## 5. Suite possible

Ces chantiers demandent des choix de direction artistique (typographie, palette).
Dis-moi lequel tu veux attaquer en premier et je l'applique directement aux
templates concernés :

- **Option A** — Chantier 1 + 3 (icons + palette) : le plus visible, le plus rapide.
- **Option B** — Chantier 2 (typographie) : le plus « signature ».
- **Option C** — Chantier 7 (finition) : le plus subtil mais le plus crédible.

