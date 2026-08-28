import 'package:flutter/material.dart';

/// Material 3 Expressive-flavoured theme: a vivid seed, heavier display type,
/// fully-rounded buttons, a soft rail. Only long-stable [ThemeData] fields are
/// set here so the app builds against any recent Flutter stable; the rounded
/// cards / pills / consoles are styled at the widget level in widgets.dart.
const Color kSeed = Color(0xFF7A5CFF);

ThemeData expressiveTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: kSeed, brightness: brightness);
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
