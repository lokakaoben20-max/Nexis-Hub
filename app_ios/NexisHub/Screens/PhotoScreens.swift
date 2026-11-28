import PhotosUI
import SwiftUI
import UIKit

// Photo de profil (personne ou entreprise) et « À propos ». La photo reste
// sur ce téléphone en attendant le serveur : l'envoi, l'affichage chez les
// autres et la suppression côté serveur arrivent avec lui.

// MARK: - Appareil photo

/// L'appareil photo du système, pour une photo de profil. L'identité garde
/// sa propre caméra guidée : ceci ne sert qu'à la photo de profil.
struct CameraPicker: UIViewControllerRepresentable {
    @Environment(\.dismiss) private var dismiss
    let onPicked: (UIImage) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.cameraDevice = .front
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ controller: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    @MainActor
    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: CameraPicker

        init(_ parent: CameraPicker) { self.parent = parent }

        func imagePickerController(_ picker: UIImagePickerController,
                                   didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let image = info[.originalImage] as? UIImage { parent.onPicked(image) }
            parent.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
}

extension UIImage {
    /// La photo réduite à 600 px au plus, compressée en JPEG.
    func profileJPEG() -> Data? {
        let longest = max(size.width, size.height)
        guard longest > 0 else { return nil }
        let scale = min(1, 600 / longest)
        let target = CGSize(width: size.width * scale, height: size.height * scale)
        let resized = UIGraphicsImageRenderer(size: target).image { _ in
            draw(in: CGRect(origin: .zero, size: target))
        }
        return resized.jpegData(compressionQuality: 0.8)
    }
}

// MARK: - Photo de profil

/// Ajouter, remplacer ou supprimer la photo. `key` : « me » pour la
/// personne, « org-<numéro> » pour une entreprise.
struct PhotoEditView: View {
    @Environment(AppModel.self) private var app
    let key: String
    @State private var profile: Profile?
    @State private var org: Organization?
    @State private var item: PhotosPickerItem?
    @State private var camera = false
    @State private var failed = false

    private var isOrg: Bool { key.hasPrefix("org-") }
    private var hasPhoto: Bool { app.photos[key] != nil }
    private var cameraAvailable: Bool { UIImagePickerController.isSourceTypeAvailable(.camera) }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                preview
                    .padding(.top, 10)
                Text(isOrg ? (org?.name ?? "") : "\(profile?.firstName ?? "") \(profile?.lastName ?? "")")
                    .font(.title(18)).foregroundStyle(Nexis.ink)
                Text(app.t("photoHint"))
                    .font(.body(14.5)).foregroundStyle(Nexis.muted)
                    .multilineTextAlignment(.center).lineSpacing(3)
                if failed {
                    Text(app.t("orgFailed")).font(.body(14)).foregroundStyle(Nexis.danger)
                }
                InfoNote(text: app.t("photoDemo"), kind: .violet)
            }
            .flowScreen()
        }
        .flowTitle(isOrg ? app.t("orgPhotoRow") : app.t("photoProfileTitle"))
        .bottomActions {
            if cameraAvailable {
                Button { camera = true } label: { WideLabel(text: app.t("photoTake"), systemImage: "camera.fill") }
                    .nxProminentButton()
            }
            PhotosPicker(selection: $item, matching: .images) {
                WideLabel(text: app.t("photoChoose"), systemImage: "photo.on.rectangle")
            }
            .nxSecondaryButton()
            if hasPhoto {
                Button(role: .destructive) {
                    app.photos[key] = nil
                } label: {
                    WideLabel(text: app.t("photoDelete"), systemImage: "trash")
                }
                .nxSecondaryButton()
            }
        }
        .fullScreenCover(isPresented: $camera) {
            CameraPicker { image in store(image) }.ignoresSafeArea()
        }
        .onChange(of: item) { _, picked in
            guard let picked else { return }
            Task {
                if let data = try? await picked.loadTransferable(type: Data.self), let image = UIImage(data: data) {
                    store(image)
                } else {
                    failed = true
                }
                item = nil
            }
        }
        .task {
            if isOrg, let id = Int(key.dropFirst(4)) {
                org = try? await app.repository.organization(id: id)
            } else {
                profile = try? await app.repository.profile()
            }
        }
    }

    @ViewBuilder
    private var preview: some View {
        if isOrg {
            OrgMark(name: org?.name ?? "", size: 132, photoKey: key)
        } else {
            InitialsAvatar(initials: profile?.initials ?? "", size: 132, photoKey: key)
        }
    }

    private func store(_ image: UIImage) {
        guard let data = image.profileJPEG() else {
            failed = true
            return
        }
        failed = false
        app.photos[key] = data
    }
}

// MARK: - À propos

struct AboutView: View {
    @Environment(AppModel.self) private var app
    @Environment(MissionFlow.self) private var flow

    private var version: String {
        let info = Bundle.main.infoDictionary
        let short = info?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = info?["CFBundleVersion"] as? String ?? "1"
        return "\(short) (\(build))"
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                VStack(spacing: 10) {
                    Text("NexisHub").font(.title(30)).foregroundStyle(Nexis.ink)
                    Text(app.t("slogan"))
                        .font(.body(15, .medium)).foregroundStyle(Nexis.softInk)
                        .multilineTextAlignment(.center)
                    Pill(tone: .info, text: app.t("aboutVersion", ["version": version]))
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 22)
                .nxCard(padding: 12)
                Text(app.t("aboutText"))
                    .font(.body(15)).foregroundStyle(Nexis.muted).lineSpacing(3)
                VStack(spacing: 0) {
                    Button { flow.push(.legal) } label: {
                        linkRow("doc.text", app.t("legalTerms"))
                    }
                    Divider().padding(.leading, 52)
                    Button { flow.comingSoon = SheetTitle(app.t("legalPrivacy")) } label: {
                        linkRow("hand.raised", app.t("legalPrivacy"))
                    }
                }
                .background(Nexis.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            }
            .flowScreen()
        }
        .flowTitle(app.t("aboutRow"))
    }

    private func linkRow(_ symbol: String, _ title: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: symbol).font(.system(size: 17, weight: .medium)).foregroundStyle(Nexis.accent)
                .frame(width: 28)
            Text(title).font(.body(16)).foregroundStyle(Nexis.ink)
            Spacer()
            Image(systemName: "chevron.right")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Color(light: 0xC4CAD4, dark: 0x4A5A75))
        }
        .padding(.horizontal, 14).padding(.vertical, 14)
        .contentShape(Rectangle())
    }
}
