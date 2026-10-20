"""Offline tests for kokoro_backend. About 30 s on a 4-vCPU sandbox.

    set ATLAS_KOKORO_DIR=C:\\AtlasVoice\\kokoro      (the folder fetch_bundle.py filled)
    py -3.12 -I test_kokoro_backend.py -v

Without ATLAS_KOKORO_DIR the tests look in ./model next to this file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kokoro_backend as kb  # noqa: E402

MODEL_DIR = Path(os.environ.get("ATLAS_KOKORO_DIR", HERE / "model"))
HAVE_BUNDLE = all((MODEL_DIR / name).is_file() for name in kb.BUNDLE)
SECRET = "Quixotic marmalade zeppelin"  # must never appear in any output stream


def samples(pcm: bytes) -> array:
    a = array("h")
    a.frombytes(pcm)
    if sys.byteorder == "big":
        a.byteswap()
    return a


@unittest.skipUnless(HAVE_BUNDLE, f"no verified bundle in {MODEL_DIR}; run fetch_bundle.py or set ATLAS_KOKORO_DIR")
class KokoroBackendTest(unittest.TestCase):
    synth: kb.SynthFn

    @classmethod
    def setUpClass(cls) -> None:
        synth, cls.rate = kb.kokoro_synth(MODEL_DIR, threads=4)
        cls.synth = staticmethod(synth)
        cls.g2p = kb.build_g2p()

    def render(self, text: str) -> list[bytes]:
        return list(self.synth(text))

    def test_rate_and_pcm_format(self) -> None:
        self.assertEqual(self.rate, 24000)
        chunks = self.render("Done. Kitchen lights off.")
        self.assertTrue(chunks)
        for c in chunks:
            self.assertIsInstance(c, bytes)
            self.assertEqual(len(c) % 2, 0)
        pcm = b"".join(chunks)
        s = samples(pcm)
        seconds = len(s) / 24000
        self.assertGreater(seconds, 1.0)
        self.assertLess(seconds, 4.0)
        peak = max(abs(x) for x in s)
        self.assertGreater(peak, 3000)  # not silence
        self.assertLessEqual(peak, 32767)

    def test_chunks_at_sentences(self) -> None:
        text = "Done: Wall Light off. Checked. The back of the house looks rather theatrical tonight, I must say."
        self.assertEqual(len(self.render(text)), len(kb.plan_chunks(self.g2p, text)))
        self.assertGreaterEqual(len(self.render(text)), 2)

    def test_first_audio_before_the_rest(self) -> None:
        text = "Lights off. " + "The battery is at sixty percent and the solar is still going strong this afternoon. " * 4
        t0 = time.perf_counter()
        it = self.synth(text)
        next(it)
        first = time.perf_counter() - t0
        list(it)
        total = time.perf_counter() - t0
        self.assertLess(first, total / 3)

    def test_empty_and_whitespace(self) -> None:
        for text in ("", " ", "\n\t  \r\n", "\u00a0\u2003"):
            self.assertEqual(self.render(text), [], repr(text))

    def test_punctuation_only_yields_nothing_or_silence(self) -> None:
        for text in ("...", "?!", "—"):
            pcm = b"".join(self.render(text))
            self.assertTrue(len(pcm) == 0 or max(abs(x) for x in samples(pcm)) < 3000, repr(text))

    def test_long_text(self) -> None:
        sentence = "The living room chandelier is on at fifty percent, and the porch lights are off. "
        long_text = sentence * 12  # about 1,000 characters, 24 sentences
        no_stops = ("and the lights are on " * 60).strip()  # 1,300 characters with no punctuation at all
        for text in (long_text, no_stops):
            chunks = self.render(text)
            self.assertGreater(len(chunks), 1)
            seconds = len(b"".join(chunks)) / 2 / 24000
            self.assertGreater(seconds, 20)
        for piece in kb.plan_chunks(self.g2p, no_stops):
            self.assertLessEqual(len(piece), kb.MAX_PHONEMES)

    def test_deterministic(self) -> None:
        text = "Timer set: Porch lights off at ten fifteen PM. Say cancel that to stop it."
        self.assertEqual(self.render(text), self.render(text))

    def test_deterministic_across_loads(self) -> None:
        text = "Good night. Everything's switched off."
        synth2, _ = kb.kokoro_synth(MODEL_DIR, threads=4)
        self.assertEqual(self.render(text), list(synth2(text)))

    def test_errors_carry_no_text(self) -> None:
        with self.assertRaises(kb.SynthesisError) as cm:
            list(self.synth(None))  # type: ignore[arg-type]
        self.assertNotIn("None", str(cm.exception).replace("NoneType", ""))

    def test_house_word_fixes(self) -> None:
        g2p = self.g2p
        self.assertIn("ɒnswˈiːt", kb.phonemize(g2p, "The ensuite light is off."))
        self.assertIn("wˈInd", kb.phonemize(g2p, "Shall I run Wind Down now?"))
        self.assertIn("ˌAˈɛm", kb.phonemize(g2p, "Lights on at seven a m."))
        self.assertTrue(kb.phonemize(g2p, "It ran at eleven p m.").endswith("."))

    def test_bad_arguments(self) -> None:
        with self.assertRaises(ValueError):
            kb.kokoro_synth(MODEL_DIR, speed=5.0)
        with self.assertRaises(ValueError):
            kb.kokoro_synth(MODEL_DIR, threads=0)


@unittest.skipUnless(HAVE_BUNDLE, f"no verified bundle in {MODEL_DIR}")
class BundleIntegrityTest(unittest.TestCase):
    """A changed, truncated or missing file must stop the load before any model is built."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="kokoro-bundle-"))
        for name in kb.BUNDLE:  # hard links where possible: fast, and the originals are never written
            try:
                os.link(MODEL_DIR / name, self.tmp / name)
            except OSError:
                shutil.copyfile(MODEL_DIR / name, self.tmp / name)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def replace(self, name: str, data: bytes) -> None:
        (self.tmp / name).unlink()
        (self.tmp / name).write_bytes(data)

    def test_intact_copy_loads(self) -> None:
        kb.verify_bundle(self.tmp)

    def test_one_flipped_byte_in_voice_fails(self) -> None:
        data = bytearray((MODEL_DIR / kb.VOICE_FILE).read_bytes())
        data[len(data) // 2] ^= 0x01
        self.replace(kb.VOICE_FILE, bytes(data))
        with self.assertRaisesRegex(kb.BundleError, "sha256 mismatch for en_GB-fablemix.npy"):
            kb.kokoro_synth(self.tmp)

    def test_changed_config_fails(self) -> None:
        data = (MODEL_DIR / kb.CONFIG_FILE).read_bytes().replace(b'"n_token": 178', b'"n_token": 179')
        self.replace(kb.CONFIG_FILE, data)
        with self.assertRaisesRegex(kb.BundleError, "config.json"):
            kb.kokoro_synth(self.tmp)

    def test_truncated_model_fails(self) -> None:
        with (MODEL_DIR / kb.MODEL_FILE).open("rb") as f:
            head = f.read(1 << 20)
        self.replace(kb.MODEL_FILE, head)
        with self.assertRaisesRegex(kb.BundleError, kb.MODEL_FILE):
            kb.kokoro_synth(self.tmp)

    def test_missing_file_fails(self) -> None:
        (self.tmp / kb.CONFIG_FILE).unlink()
        with self.assertRaisesRegex(kb.BundleError, "cannot read"):
            kb.kokoro_synth(self.tmp)


@unittest.skipUnless(HAVE_BUNDLE, f"no verified bundle in {MODEL_DIR}")
class IsolationTest(unittest.TestCase):
    """Load and synthesise in a fresh interpreter that records every network attempt and all output."""

    CHILD = textwrap.dedent(
        """
        import logging, sys
        BLOCK = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
                 "socket.sendto", "socket.sendmsg", "urllib.Request", "http.client.connect", "ftplib.connect",
                 "smtplib.connect", "webbrowser.open", "os.system", "os.startfile")
        blocked, other, procs = [], [], []
        def hook(event, args):
            if event in BLOCK:
                blocked.append(event)
                raise PermissionError("blocked by test: " + event)
            if event == "socket.bind":
                other.append(("bind", str(args[1])))
            if event == "subprocess.Popen":
                procs.append(str(args[0]).replace("\\\\", "/").rsplit("/", 1)[-1])
        sys.addaudithook(hook)
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)  # surface anything any library logs
        sys.path.insert(0, sys.argv[1])
        import kokoro_backend as kb
        synth, rate = kb.kokoro_synth(sys.argv[2], threads=2)
        n = sum(len(c) for c in synth(sys.argv[3] + ". Done: Fountain Spotlight on. Checked."))
        print("BLOCKED", blocked, "BINDS", other, "BYTES", n, "RATE", rate, "PROCS", sorted(set(procs)))
        """
    )

    def test_no_network_and_no_text_in_output(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.upper().endswith("_PROXY")}
        env["HTTPS_PROXY"] = env["HTTP_PROXY"] = "http://127.0.0.1:9"  # a dead proxy, should anything try
        proc = subprocess.run(
            [sys.executable, "-I", "-c", self.CHILD, str(HERE), str(MODEL_DIR), SECRET],
            capture_output=True, text=True, timeout=300, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertIn("BLOCKED [] ", proc.stdout)  # no connect, DNS lookup, send, URL open or child process
        # urllib3 (imported by spaCy through requests) binds ::1 port 0 once at import to probe for IPv6. That is
        # the only socket activity allowed: loopback, never connected, nothing sent.
        binds = proc.stdout.split("BINDS ")[1].split(" BYTES")[0]
        self.assertIn(binds, ("[]", "[('bind', \"('::1', 0)\")]"))
        self.assertIn("RATE 24000", proc.stdout)
        # Child processes: none on Windows. On Linux only ctypes.util.find_library's ldconfig/gcc probe, run when
        # phonemizer imports dlinfo (it does not on Windows).
        procs = proc.stdout.split("PROCS ")[1].strip()
        allowed = ("[]",) if sys.platform == "win32" else ("[]", "['ldconfig']", "['gcc', 'ldconfig']", "['ld', 'ldconfig']")
        self.assertIn(procs, allowed)
        self.assertGreater(int(proc.stdout.split("BYTES ")[1].split()[0]), 48000)
        streams = (proc.stdout + proc.stderr).lower()
        for word in SECRET.lower().split() + ["fountain", "spotlight"]:
            self.assertNotIn(word, streams)


if __name__ == "__main__":
    unittest.main()
