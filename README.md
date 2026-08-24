# MNIST in HTML + CSS

This is the first step toward expressing a neural network in HTML and CSS: a
784-to-32-to-10 ReLU MNIST MLP whose forward pass is evaluated by the browser's
CSS engine. The page includes ten selectable test images—one of each digit—and
recomputes the classifier whenever the selected radio button changes.

There is no JavaScript in the generated page. Python is used at build time to:

1. download MNIST,
2. train a multinomial linear classifier,
3. export its weights and ten test images as CSS custom properties, and
4. write the static HTML visualization.

At runtime, each hidden activation and class score is a CSS expression:

```css
--hidden-pre-00: calc(
  var(--hidden-bias-00)
  + var(--x-000) * var(--hidden-w-00-000)
  + var(--x-001) * var(--hidden-w-00-001)
  /* ... */
);

--hidden-00: max(0, var(--hidden-pre-00));
```

The class with the longest bar is the CSS prediction. Python's reference
prediction is shown only as a correctness check. Selecting an image is handled
with radio inputs and `:has()`; there is still no JavaScript at runtime.

## Build

```sh
make build
open index.html
```

The first build downloads `mnist.npz` (about 11 MB) and trains the model. The
dataset is cached under `data/` and excluded from version control.

Requirements: Python 3 and NumPy. The generated page needs a browser supporting
CSS typed arithmetic (`*` in `calc()`), such as a current Chromium release.
