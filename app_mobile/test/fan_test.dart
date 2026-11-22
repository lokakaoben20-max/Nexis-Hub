import 'package:flutter_test/flutter_test.dart';
import 'package:nexis_hub/screens/welcome_intro.dart';

void main() {
  test('chute des cartes : hors écran au départ, posée à la fin, rebonds', () {
    expect(VerifiedFan.pose(0), (-820.0, 0.0));
    expect(VerifiedFan.pose(1), (0.0, 1.0));
    // Premier contact au sol à 52 %, puis rebond de 22 px vers le haut.
    expect(VerifiedFan.pose(.52).$1, closeTo(0, 1e-6));
    expect(VerifiedFan.pose(.68).$1, closeTo(-22, 1e-6));
    expect(VerifiedFan.pose(.80).$1, closeTo(0, 1e-6));
    expect(VerifiedFan.pose(.89).$1, closeTo(-7, 1e-6));
    expect(VerifiedFan.pose(.96).$1, closeTo(0, 1e-6));
    // Complètement visible dès 6 % de la chute.
    expect(VerifiedFan.pose(.06).$2, 1.0);
  });
}
