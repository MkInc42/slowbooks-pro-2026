# Accessibility

SlowBooks Pro is built to be usable by everyone, including people who rely
on screen readers, keyboards, or high-contrast displays. We **strive to
conform to WCAG 2.1 Level AA**. We do not claim compliance — no certifying
body issues one — but we test against it, fix what we find, and treat a
barrier as a bug.

![The Company Snapshot split down the middle: the light theme on the left, the dark theme on the right, with the same figures and the same A/R aging colour key in both](../screenshots/a11y-split.png)

*The same screen in both themes. Switch with the theme button in the toolbar,
or Alt+D.*

## What is in place (v2.19.0)

### Contrast, in both themes

- Text meets **WCAG AA contrast** (4.5:1, or 3:1 for large text: 24px, or
  18.66px bold) in the light and the dark theme everywhere it is drawn: every
  page, 142 dialogs, the sign-in and setup screens, pop-up messages and the
  PDF window. Semi-transparent text is measured as it is painted. (v2.18.0)
- Chart lines, bars and colour keys meet **3:1** (WCAG 1.4.11), so the A/R
  aging colours can be told apart in both themes. (v2.18.0)
- **How it's checked:** `tests/test_theme_contrast.py`,
  `tests/test_dialog_contrast.py` and `tests/test_css_hidden_and_contrast.py`
  open every page, notice and dialog in Chromium in both themes and measure
  the colours actually painted. They run with the suite before each release
  (they skip where playwright's Chromium isn't installed), and the macOS
  release gate carries its own contrast rules.

### Screen readers and keyboards

- **The pickers search as you type** (v2.19.0): each is a WAI-ARIA 1.2
  combobox, so a screen reader hears its name, how many names match as you
  type, and the highlighted one. The arrow keys move through the list, Enter
  or Tab takes a name, and Escape backs out.
- **Every form field has a name a screen reader can say** (v2.18.2, #198):
  a form's label is tied to its field (clicking the label puts the cursor in
  the field), a required field is read as required rather than as "star",
  a field in a grid of inputs is named from its column and row ("Jan, 6500
  Rent or Lease"), a checkbox that starts a row says what ticking it
  does ("Pay invoice 1001"), and a field with only a placeholder, like a
  search box, takes it as its name (VoiceOver reads it that way too). Fields with the same label in different parts
  of a screen sit in groups named after their headings (Billing Address,
  Shipping Address). `tests/test_field_names.py` sweeps every page and
  dialog, a nonprofit's included, for a field without a name (2.18.1 had
  about 1,100) and for two fields a screen reader couldn't tell apart.
- **Every PDF the app generates is tagged (PDF/UA-1)** and declares its
  language and title — invoices, statements, estimates, pay stubs, W-2s,
  1099s, Forms 940/941, checks, reports — so screen readers receive
  headings, tables and reading order rather than a flat image of text.
- **Dialogs are real dialogs:** focus moves into them, Tab and Shift+Tab stay
  inside, Escape closes them, and focus returns to the control that opened
  them. Tab reaches every control, buttons and links included, on every
  browser and whatever the Mac's "keyboard navigation" setting: the dialog
  moves focus itself, in the order the browser would (v2.22.0). Escape in
  a date field leaves the field (after closing its calendar); the next
  Escape closes the dialog, so an unsaved form is not lost to one key
  (v2.22.0). No dialog opens with focus on Void or Delete: one whose first
  control is destructive takes focus itself, and reads its title (v2.22.0).
- **Back, within the app** (v2.22.0): the toolbar's ← button goes back
  through the app's history, and is enabled only while an app page is
  behind. The desktop app's window has no Back of its own, and some hops (a
  report's row to a customer's page, a class's page to its P&L) have no
  "Back to …" button; this covers them all.

### Keyboard shortcuts

| Keys | Does |
|---|---|
| Alt+← (⌘[ on a Mac) | Back, within the app |
| Alt+N | New invoice |
| Alt+P | Receive payment |
| Alt+Q | Quick Entry |
| Alt+H | Dashboard |
| Alt+D | Toggle dark mode |
| Ctrl+K (⌘K on a Mac), or `/` outside a field | Search |
| Ctrl+S | Save the open form |
| Ctrl+Enter | Submit Quick Entry |
| Escape | Close the dialog (in a date field: leave the field first) |

On a Mac the Alt key is Option; the letter shortcuts go by the key, not
the character Option types, so Option-D toggles the theme even though it
types "∂" (v2.22.0).
- **Notifications** ("Invoice saved") announce through a polite live region.
- **Every data table declares its column headers** (`scope="col"`).
- **Icon-only buttons** (remove a line, delete an attachment, close a dialog)
  carry accessible names.
- **State is never conveyed by colour alone:** an invoice reads Paid, Draft or
  Sent; a reconciliation reads "Balanced" or "Out of balance".

![The New Invoice dialog with keyboard focus in the Date field](../screenshots/a11y-dialog.png)

*New Invoice: focus is inside the dialog and moves from field to field with
Tab.*

## What we know is still open

- The chart-of-accounts tree and some long entry forms could use landmark
  regions and skip links.
- Colour-coding on the dashboard charts has text equivalents in the legend
  but not on the bars themselves.
- Keyboard-only drag ordering is not offered where a mouse drag exists
  (the dashboard uses arrow buttons instead).

## Tell us

If something in SlowBooks Pro is hard or impossible for you to use, open
an issue at https://github.com/VonHoltenCodes/SlowBooks-Pro-2026/issues or
email trent@neonpulsetechshop.com and say which screen and which assistive
technology. Barriers are triaged as bugs.

The same statement, with more screenshots, is on the website:
https://www.slowbookspro.com/accessibility/
