import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/ui/phone.dart';

void main() {
  test('mise en forme pendant la saisie', () {
    expect(DrcPhone.parse('8').formatted, '8');
    expect(DrcPhone.parse('81').formatted, '81');
    expect(DrcPhone.parse('812').formatted, '81 2');
    expect(DrcPhone.parse('812345').formatted, '81 234 5');
    expect(DrcPhone.parse('812345454').formatted, '81 234 54 54');
    expect(DrcPhone.parse('81234545499').formatted, '81 234 54 54');
  });

  test('+243, 00243 et 0 d\'appel sont retirés', () {
    expect(DrcPhone.parse('+243 812 345 454').digits, '812345454');
    expect(DrcPhone.parse('00243812345454').digits, '812345454');
    expect(DrcPhone.parse('0812345454').digits, '812345454');
    expect(DrcPhone.parse('+243812345454').e164, '+243812345454');
  });

  test('opérateurs et validité', () {
    expect(DrcPhone.parse('812345454').operator, Operator.vodacom);
    expect(DrcPhone.parse('972345454').operator, Operator.airtel);
    expect(DrcPhone.parse('852345454').operator, Operator.orange);
    expect(DrcPhone.parse('902345454').operator, Operator.africell);
    expect(DrcPhone.parse('812345454').isValid, isTrue);
    expect(DrcPhone.parse('81234545').isValid, isFalse); // incomplet
    expect(DrcPhone.parse('702345454').isValid, isFalse); // préfixe inconnu
    expect(DrcPhone.parse('7').prefixKnown, isTrue);
    expect(DrcPhone.parse('70').prefixKnown, isFalse);
  });

  test('le formateur garde le curseur à la fin', () {
    const f = DrcPhoneFormatter();
    final v = f.formatEditUpdate(
      TextEditingValue.empty,
      const TextEditingValue(text: '81234'),
    );
    expect(v.text, '81 234');
    expect(v.selection.baseOffset, 6);
  });
}
