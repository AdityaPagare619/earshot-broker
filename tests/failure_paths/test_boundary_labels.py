"""F8: honest boundary labels are a tested registry, not prose.

Every limitation from dossier section 17 ("not completed or claimed") has an
exact user-facing label. Labels must not contain overclaim words. If a new
limitation is added to the docs without a registry entry, this test fails.
"""
import re
import unittest

# The registry: limitation -> exact user-facing label.
# Source: EARSHOT_REDESIGN.md section 17, "Not completed or claimed".
BOUNDARIES = {
    'no_device_integration':
        'Demonstration only: no connection to a real Alexa+ device or the '
        'official Alexa simulator was used.',
    'no_production_oauth':
        'No production OAuth deployment. Tokens shown are test fixtures.',
    'no_live_provider':
        'No live calendar or data-provider connection. All records are '
        'synthetic fixtures.',
    'no_camera_model':
        'No camera, face, or occupancy model was evaluated. Presence input '
        'is manual or simulated and labeled as such.',
    'no_audio_cancellation':
        'No real audio cancellation was measured. Speech stop is demonstrated '
        'in the controlled web host only.',
    'no_real_phone':
        'No real phone notification was sent. Delivery is demonstrated '
        'against a test inbox.',
    'no_bedrock_call':
        'No Bedrock, model, or Kiro runtime call was made in this build.',
    'no_crypto_capsule':
        'No production cryptographic capsule. Sealed tasks are a '
        'server-side data model, not an encryption claim.',
    'no_perf_benchmark':
        'No performance benchmark. Timings shown are functional checks, '
        'not production latency claims.',
    'no_certification':
        'No Alexa certification review has been passed. Certification '
        'questions about intentional non-disclosure remain open.',
    'simulated_presence':
        'Room presence is simulated input. It does not prove real-world '
        'listener detection.',
    'no_memory_erasure':
        'Withdrawing a request does not erase already-emitted sound, pixels, '
        'or third-party memory.',
}

OVERCLAIM_WORDS = ('certified', 'guaranteed', 'production-grade',
                   'real-time', 'military-grade', 'zero-leak', 'unhackable')

# Dossier section-17 items that must each have a registry entry.
REQUIRED_COVERAGE = (
    'no_device_integration', 'no_production_oauth', 'no_live_provider',
    'no_camera_model', 'no_audio_cancellation', 'no_real_phone',
    'no_bedrock_call', 'no_crypto_capsule', 'no_perf_benchmark',
    'no_certification', 'simulated_presence', 'no_memory_erasure',
)


class BoundaryLabelTests(unittest.TestCase):
    def test_registry_covers_all_required(self):
        for key in REQUIRED_COVERAGE:
            self.assertIn(key, BOUNDARIES, f'missing boundary label: {key}')

    def test_labels_are_plain_language(self):
        for key, label in BOUNDARIES.items():
            self.assertTrue(len(label) >= 20, f'label too terse: {key}')
            self.assertTrue(label[0].isupper(), f'label must start capitalized: {key}')

    def test_no_overclaim_words(self):
        for key, label in BOUNDARIES.items():
            low = label.lower()
            for word in OVERCLAIM_WORDS:
                # 'certified' may appear only inside an explicit negation
                if word == 'certified':
                    if 'certified' not in low and 'certification' not in low:
                        continue
                    self.assertTrue(
                        re.search(r'not certified|no .*certification', low),
                        f'bare "certified" claim in {key}')
                    continue
                self.assertNotIn(word, low,
                                 f'overclaim word {word!r} in boundary {key}')

    def test_simulated_presence_label_names_the_limit(self):
        self.assertIn('simulated', BOUNDARIES['simulated_presence'].lower())
        self.assertIn('does not prove', BOUNDARIES['simulated_presence'].lower())


if __name__ == '__main__':
    unittest.main()
