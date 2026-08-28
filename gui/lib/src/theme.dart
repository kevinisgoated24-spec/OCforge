import 'package:flutter/material.dart';

/// Selectable accent palettes. Each seeds a full Material 3 scheme, so the
/// whole app (buttons, chips, rail, glyph) recolours from one value.
enum AccentTheme {
  violet(Color(0xFF7A5CFF), 'Violet'),
  indigo(Color(0xFF4C6FFF), 'Indigo'),
  emerald(Color(0xFF0FA968), 'Emerald'),
  amber(Color(0xFFE8930C), 'Amber'),
  rose(Color(0xFFE84A7F), 'Rose'),
  cyan(Color(0xFF0CA5B8), 'Cyan'),
  slate(Color(0xFF5B6B7C), 'Slate');

  const AccentTheme(this.seed, this.label);

  final Color seed;
  final String label;

  static AccentTheme byName(String? name) =>
      values.firstWhere((AccentTheme a) => a.name == name,
          orElse: () => AccentTheme.violet);
}

/// Kept for anything still importing it; the live seed is [AccentTheme.seed].
const Color kSeed = Color(0xFF7A5CFF);

/// Material 3 Expressive-flavoured theme: a vivid seed, heavier display type,
/// fully-rounded buttons, a soft rail. Only long-stable [ThemeData] fields are
/// set here so the app builds against any recent Flutter stable; the rounded
/// cards / pills / consoles are styled at the widget level in widgets.dart.
ThemeData expressiveTheme(Brightness brightness, {Color seed = kSeed}) {
  final scheme = ColorScheme.fromSeed(seedColor: seed, brightness: brightness);
  final base = ThemeData(useMaterial3: true, colorScheme: scheme);

  final text = base.textTheme.copyWith(
    displaySmall: base.textTheme.displaySmall?.copyWith(
      fontWeight: FontWeight.w700,
      letterSpacing: -0.5,
    ),
    headlineMedium: base.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
    headlineSmall: base.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w600),
    titleLarge: base.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
    labelLarge: base.textTheme.labelLarge?.copyWith(
      fontWeight: FontWeight.w600,
      letterSpacing: 0.1,
    ),
  );

  return base.copyWith(
    textTheme: text,
    scaffoldBackgroundColor: scheme.surface,
    splashFactory: InkSparkle.splashFactory,
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        shape: const StadiumBorder(),
        padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 18),
        textStyle: text.labelLarge?.copyWith(fontSize: 15),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        shape: const StadiumBorder(),
        padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(shape: const StadiumBorder()),
    ),
    navigationRailTheme: NavigationRailThemeData(
      backgroundColor: scheme.surface,
      indicatorColor: scheme.secondaryContainer,
      indicatorShape: const StadiumBorder(),
      selectedIconTheme: IconThemeData(color: scheme.onSecondaryContainer),
      unselectedIconTheme: IconThemeData(color: scheme.onSurfaceVariant),
      labelType: NavigationRailLabelType.all,
    ),
  );
}
