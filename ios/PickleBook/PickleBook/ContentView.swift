// ContentView.swift
// PickleBook
//
// Main screen: toggle switch, status display, and manual booking trigger.

import SwiftUI

// ---------------------------------------------------------------------------
// MARK: - View Model
// ---------------------------------------------------------------------------

@MainActor
class BookingViewModel: ObservableObject {
    @Published var status: BookingStatus?
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var serverURL: String {
        didSet {
            UserDefaults.standard.set(serverURL, forKey: "serverURL")
        }
    }
    @Published var showSettings = false

    private let service = BookingService()
    private var pollTask: Task<Void, Never>?

    init() {
        self.serverURL = UserDefaults.standard.string(forKey: "serverURL")
            ?? "http://192.168.1.100:8787"
    }

    // MARK: - Polling

    func startPolling() {
        pollTask?.cancel()
        pollTask = Task {
            while !Task.isCancelled {
                await refresh()
                try? await Task.sleep(for: .seconds(30))
            }
        }
    }

    func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    // MARK: - Actions

    func refresh() async {
        do {
            let s = try await service.fetchStatus()
            status = s
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func toggle() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let s = try await service.toggle()
            status = s
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func bookNow() async {
        isLoading = true
        defer { isLoading = false }
        // For manual trigger we just ensure it is enabled then refresh
        do {
            let s = try await service.setEnabled(true)
            status = s
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// ---------------------------------------------------------------------------
// MARK: - Content View
// ---------------------------------------------------------------------------

struct ContentView: View {
    @StateObject private var vm = BookingViewModel()

    // Pickle green
    private let accentGreen = Color(red: 0.40, green: 0.70, blue: 0.20)

    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 28) {
                    statusCard
                    toggleSection
                    detailsSection
                    bookNowButton
                    errorBanner
                }
                .padding(.horizontal, 20)
                .padding(.top, 12)
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("PickleBook")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        vm.showSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $vm.showSettings) {
                settingsSheet
            }
            .onAppear { vm.startPolling() }
            .onDisappear { vm.stopPolling() }
            .refreshable { await vm.refresh() }
        }
        .tint(accentGreen)
    }

    // MARK: - Status Card

    private var statusCard: some View {
        HStack(spacing: 14) {
            Circle()
                .fill(isEnabled ? Color.green : Color.red)
                .frame(width: 16, height: 16)
                .shadow(color: isEnabled ? .green.opacity(0.5) : .red.opacity(0.5), radius: 6)

            Text(isEnabled ? "Auto-Booking Active" : "Auto-Booking Paused")
                .font(.headline)

            Spacer()
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    // MARK: - Toggle

    private var toggleSection: some View {
        VStack(spacing: 12) {
            Text("Auto-Book Courts")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Toggle("", isOn: Binding(
                get: { isEnabled },
                set: { _ in
                    Task { await vm.toggle() }
                }
            ))
            .toggleStyle(LargeToggleStyle(accentColor: accentGreen))
            .labelsHidden()
            .disabled(vm.isLoading)
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    // MARK: - Details

    private var detailsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            detailRow(icon: "calendar", title: "Next Booking",
                      value: vm.status?.nextBookingDate ?? "---")
            Divider()
            detailRow(icon: "clock", title: "Last Run",
                      value: vm.status?.lastRun ?? "Never")
            Divider()
            detailRow(icon: "checkmark.circle", title: "Last Result",
                      value: vm.status?.lastResult ?? "---")
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private func detailRow(icon: String, title: String, value: String) -> some View {
        HStack {
            Label(title, systemImage: icon)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline.monospacedDigit())
                .foregroundStyle(.primary)
        }
    }

    // MARK: - Book Now

    private var bookNowButton: some View {
        Button {
            Task { await vm.bookNow() }
        } label: {
            HStack {
                if vm.isLoading {
                    ProgressView()
                        .tint(.white)
                }
                Text("Book Now")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .disabled(vm.isLoading)
    }

    // MARK: - Error

    @ViewBuilder
    private var errorBanner: some View {
        if let error = vm.errorMessage {
            Text(error)
                .font(.caption)
                .foregroundStyle(.red)
                .multilineTextAlignment(.center)
                .padding()
                .frame(maxWidth: .infinity)
                .background(Color.red.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
        }
    }

    // MARK: - Settings Sheet

    private var settingsSheet: some View {
        NavigationView {
            Form {
                Section("Server URL") {
                    TextField("http://192.168.1.100:8787", text: $vm.serverURL)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                }
                Section {
                    Text("The app connects to your local PickleBook server to control auto-booking.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        vm.showSettings = false
                        Task { await vm.refresh() }
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    private var isEnabled: Bool {
        vm.status?.enabled ?? false
    }
}

// ---------------------------------------------------------------------------
// MARK: - Custom Large Toggle Style
// ---------------------------------------------------------------------------

struct LargeToggleStyle: ToggleStyle {
    let accentColor: Color

    func makeBody(configuration: Configuration) -> some View {
        HStack {
            configuration.label
            Spacer()
            ZStack {
                Capsule()
                    .fill(configuration.isOn ? accentColor : Color(.systemGray4))
                    .frame(width: 80, height: 44)

                Circle()
                    .fill(.white)
                    .shadow(radius: 2)
                    .frame(width: 38, height: 38)
                    .offset(x: configuration.isOn ? 18 : -18)
                    .animation(.spring(response: 0.3), value: configuration.isOn)
            }
            .onTapGesture {
                configuration.isOn.toggle()
            }
        }
    }
}

// ---------------------------------------------------------------------------
// MARK: - Preview
// ---------------------------------------------------------------------------

#Preview {
    ContentView()
}
