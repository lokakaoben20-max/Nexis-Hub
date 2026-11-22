/// Jours et heures dans la langue de l'app (les noms lingala sont à
/// relire par une personne de Kinshasa).
const _weekdays = {
  'fr': [
    'lundi',
    'mardi',
    'mercredi',
    'jeudi',
    'vendredi',
    'samedi',
    'dimanche',
  ],
  'ln': [
    'mokɔlɔ ya yambo',
    'mokɔlɔ ya mibale',
    'mokɔlɔ ya misato',
    'mokɔlɔ ya minei',
    'mokɔlɔ ya mitano',
    'mposɔ',
    'lomingo',
  ],
  'en': [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
  ],
};

/// « 9 h », « 8 h 41 » ; en anglais « 9 am », « 8:41 am ».
String formatClock(DateTime time, String lang) {
  final m = time.minute;
  if (lang == 'en') {
    final h = time.hour % 12 == 0 ? 12 : time.hour % 12;
    final suffix = time.hour < 12 ? 'am' : 'pm';
    return m == 0 ? '$h $suffix' : '$h:${m.toString().padLeft(2, '0')} $suffix';
  }
  return m == 0
      ? '${time.hour} h'
      : '${time.hour} h ${m.toString().padLeft(2, '0')}';
}

/// « samedi 9 h » (ou « Samedi 9 h » avec [capital]).
String formatSlot(DateTime time, String lang, {bool capital = false}) {
  final days = _weekdays[lang] ?? _weekdays['fr']!;
  final day = days[time.weekday - 1];
  final text = '$day ${formatClock(time, lang)}';
  return capital ? text[0].toUpperCase() + text.substring(1) : text;
}

const _shortWeekdays = {
  'fr': ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'],
  'en': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
};

/// Heure d'un événement : « 13 h » aujourd'hui, sinon « sam. 13 h »
/// (le lingala garde le nom entier du jour).
String formatStamp(DateTime time, String lang, {DateTime? now}) {
  final today = now ?? DateTime.now();
  final sameDay =
      time.year == today.year &&
      time.month == today.month &&
      time.day == today.day;
  if (sameDay) return formatClock(time, lang);
  final days = _shortWeekdays[lang] ?? _weekdays[lang] ?? _weekdays['fr']!;
  return '${days[time.weekday - 1]} ${formatClock(time, lang)}';
}

/// Jours entiers qui restent avant [until] (au moins 1 tant que ce n'est
/// pas passé, 0 ensuite).
int daysLeft(DateTime until, {DateTime? now}) {
  final left = until.difference(now ?? DateTime.now());
  if (left.isNegative || left == Duration.zero) return 0;
  return (left.inMinutes / (24 * 60)).ceil();
}
