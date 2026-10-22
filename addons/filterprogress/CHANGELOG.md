# Changelog — Filter Progress

[Read Me](README.md) ● [Change Log](CHANGELOG.md)

All notable changes to this addon. Newest first.

## 2.0.0
This release turns the addon into a regular registered plugin. The Cancel button works the same way as before.

### Changed
- The code moved out of `filterprogress.gpr.py` into a new module, `filterprogress.py`. The `.gpr.py` file now only registers the addon.
- Gramps now runs the code once at startup, through `load_on_reg`. Before, it ran every time Gramps scanned its plugins, including when the Addon Manager checked an addon archive before installing it.
- **Filter Progress** now appears in the Plugin Manager, and **Deactivate** turns it off after a restart. Before, it could not be turned off without removing its folder.
- Only the filter methods that exist in the running Gramps are replaced: `check_func()` and `check_and()` on Gramps 5.2, `apply_logical_op_to_all()` on Gramps 6.0.2 and later. Before, the Gramps 5.2 replacements were installed on Gramps 6.0 too.
- Messages go to the Gramps log (logger `.filterprogress`) instead of the terminal. Debug messages appear only when Gramps starts with `gramps -d ".filterprogress"`.

### Fixed
- On Gramps 6.0, a line was printed in the terminal every time a filter ran (`new_apply_logical_op_to_all, user: ...`). It is now a debug message.
- On Gramps 6.0, the progress bar could close before reaching the end when most people were skipped early by the filter optimizer. It now reaches the end.
- On Gramps 5.2, the progress window text "Applying ..." was not translated for one kind of filter. It now is.

### Notes
- Earlier copies had no version number. If one was installed by hand, replace the whole `filterprogress` folder.

## Original (Kari Kujansuu, 2024)
- A single `filterprogress.gpr.py` file that added a **Cancel** button to the filter progress window of Gramps 5.2.
- Later extended for Gramps 6.0.2 and later, where Gramps shows no filter progress window at all.
