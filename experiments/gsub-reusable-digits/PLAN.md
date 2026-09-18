# Reuse the digits, retain the connected calculation

The earlier compiler assigned different digit glyphs to every position and
intermediate result. This attempt shares sixteen digit glyphs and thirty-two
temporary addition-result glyphs across the entire calculation. Explicit
accumulator and operand markers identify which two numbers are being combined.

The numerical contract remains signed integer inputs −8 through 7, repeating
weights `[3, −2, 5, 1]`, an exact connected sum, and an internal `2S+1` operation.
CSS receives only the final number through the same native geometry reader.
Four base-16 digits provide enough room through 256 inputs. No full-vector
lookup table or change in numerical precision is allowed.

1. Build the four-input font; check every one of its 65,536 input vectors in
   Chrome, including the native numerical consumer. Disable stages and break
   shaping boundaries to verify the connected path matters.
2. If that passes, build 16 and 64 inputs. Check extrema, cancellation,
   carry-related examples, every individual input, and seeded random vectors.
3. If those pass, try 256 inputs. This exceeds the earlier compiler's current
   character-allocation and glyph-allocation limits. Treat any failure as an
   observed limit of this implementation, not a proof of impossibility.
4. Compare the new and retained old sequential fonts at 4, 16, and 64 inputs.
   Use the same raw inputs and final CSS consumer, batch size 256, and three
   fresh browser runs with different seeds. Each timing phase uses five warmup
   samples followed by twenty measured samples. Reverse variant order in one
   repetition. Each font backend is paired with direct CSS as a context control.
5. Report exact glyph/rule/font-size growth, correctness, and complete-update
   timings. Shared glyphs alone are not evidence of a speed improvement.

Each reduction pass has fresh top-level lookup IDs but shares the small nested
digit-addition tables. This deliberately retains a linear number of lookup
wrappers: repeating one lookup ID does not guarantee repeated application by a
font shaper. Marker routing may cost more work than the previous position tags.

All builds, shaping diagnostics, and browser runs use the shared isolation
lock. Existing fonts and harnesses are preserved; this experiment has its own
compiler, test driver, copied retained-font controls, and evidence files.
