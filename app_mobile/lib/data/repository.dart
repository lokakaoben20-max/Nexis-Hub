import 'models.dart';
import 'money.dart';

/// Ce que les écrans lisent. Une seule source : le serveur Nexis.
///
/// Aujourd'hui seule l'implémentation de démonstration existe (aperçu
/// avec données fictives). La connexion au serveur (/api/app/v1, appareils
/// et sessions déjà en place côté backend) viendra la remplacer sans
/// changer les écrans.
abstract class NexisRepository {
  /// Canaux par lesquels le serveur envoie réellement un code (`whatsapp`,
  /// `telegram`, `sms`), comme `AVAILABLE_DELIVERIES` côté backend
  /// (backend/app/app_auth.py). Un canal absent n'est pas montré : jamais
  /// d'option qui fait semblant.
  Set<String> get codeChannels;

  /// Parcours de démonstration, après la vérification fictive du numéro.
  bool openDemoAccount(String phone);

  List<String> get signupCommunes;
  DateTime get signupTermsVersion;

  /// Crée et sélectionne le profil fictif seulement si ses CGU sont acceptées.
  bool registerDemoClient({
    required String phone,
    required String firstName,
    required String lastName,
    required String commune,
    required DateTime? acceptedTermsVersion,
  });

  Future<Profile> profile();
  Future<Wallet> wallet();
  Future<List<Mission>> missions();
  Future<List<Movement>> movements();

  Future<Mission> mission(int id);

  /// Le catalogue des services, dans l'ordre voulu par le serveur.
  Future<List<CatalogService>> serviceCatalog();

  /// « Décrire mon besoin » : une demande libre, transmise à l'équipe.
  Future<void> sendFreeRequest(String title, String text);

  /// Les devis reçus pour une mission, le mieux noté en premier.
  Future<List<Quote>> quotes(int missionId);

  Future<List<PayAccount>> payAccounts();

  /// Demande le paiement du devis choisi à l'opérateur. Le montant est
  /// celui du devis enregistré sur le serveur, jamais un calcul de l'app.
  Future<Mission> pay(int missionId, int quoteId, MobileOperator operator);

  /// Le client confirme que le travail est fait : le serveur verse
  /// l'argent sécurisé au prestataire.
  Future<Mission> confirmDone(int missionId);

  /// Le litige de la mission, s'il y en a un.
  Future<Dispute?> dispute(int missionId);

  /// Le client signale un problème : le serveur ouvre le litige et bloque
  /// l'argent sécurisé de la mission jusqu'à la décision. Refusé si la
  /// mission n'a pas d'argent sécurisé ou si le délai de 48 h est passé.
  Future<Dispute> reportProblem(
    int missionId,
    DisputeReason reason,
    String text,
  );

  // --- Espace prestataire ---

  Future<ProviderHome> providerHome();

  /// « En service » : reçoit ou non les nouvelles demandes.
  Future<void> setInService(bool value);

  Future<ProviderRequest> providerRequest(int missionId);

  /// Envoie un devis. Le serveur refuse un prix nul ou négatif, une
  /// mission qui n'est plus ouverte, ou un prestataire client de la
  /// mission.
  Future<void> sendQuote(int missionId, Money price, DateTime slot);

  Future<ProviderJob> providerJob(int missionId);

  Future<ProviderJob> setSharing(int missionId, bool value);

  /// « Je suis parti ».
  Future<ProviderJob> leaveForJob(int missionId);

  /// « Je suis arrivé » : prévient le client, ne confirme rien seul.
  Future<ProviderJob> signalArrival(int missionId);

  /// Le code de présence du client, tapé par le prestataire. Cinq essais
  /// au plus ; ensuite seul l'appui du client confirme.
  Future<PresenceResult> enterPresenceCode(int missionId, String code);

  /// « J'ai terminé » : le client a 48 h pour confirmer ou signaler.
  Future<ProviderJob> finishJob(int missionId);
}
