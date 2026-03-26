"""
Génère l'icône EnterpriseCore en PNG pur Python (sans dépendances externes).
"""
import struct
import zlib
import math
import os


def write_png(path: str, width: int, height: int, pixels: list):
    """Écrit un fichier PNG RGB valide."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        crc = struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + payload + crc

    raw = b""
    for row in pixels:
        raw += b"\x00"
        for r, g, b in row:
            raw += bytes([r, g, b])

    sig   = b"\x89PNG\r\n\x1a\n"
    ihdr  = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    idat  = chunk(b"IDAT", zlib.compress(raw, 9))
    iend  = chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(sig + ihdr + idat + iend)


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_icon(size=512):
    pixels = []

    # Couleurs
    bg1   = (15,  17,  23)   # fond sombre
    bg2   = (26,  29,  45)   # fond légèrement plus clair (centre)
    ring1 = (91, 106, 245)   # bleu-violet accent
    ring2 = (124, 58, 237)   # violet
    text  = (226, 232, 240)  # blanc doux

    cx, cy = size / 2, size / 2
    R = size * 0.42          # rayon cercle principal
    ring_w = size * 0.045    # épaisseur anneau

    for y in range(size):
        row = []
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            # Fond gradient radial
            t_bg = min(1.0, dist / (size * 0.6))
            px = lerp_color(bg2, bg1, t_bg)

            # Anneau extérieur (dégradé angulaire)
            if R - ring_w <= dist <= R + ring_w:
                angle = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)
                ring_col = lerp_color(ring1, ring2, angle)
                smooth = 1.0 - abs(dist - R) / ring_w
                smooth = max(0, min(1, smooth)) ** 0.5
                px = lerp_color(px, ring_col, smooth * 0.95)

            # Lettre "E" (gauche)
            e_x = cx - size * 0.165
            e_top = cy - size * 0.185
            e_bot = cy + size * 0.185
            e_mid_y1 = cy - size * 0.025
            e_mid_y2 = cy + size * 0.025
            bar_w = size * 0.032
            arm_l = size * 0.135
            arm_l_mid = size * 0.10

            in_e = False
            # Barre verticale
            if e_x - bar_w <= x <= e_x + bar_w and e_top <= y <= e_bot:
                in_e = True
            # Barre haut
            if e_x <= x <= e_x + arm_l and e_top <= y <= e_top + bar_w * 1.5:
                in_e = True
            # Barre milieu
            if e_x <= x <= e_x + arm_l_mid and e_mid_y1 <= y <= e_mid_y2:
                in_e = True
            # Barre bas
            if e_x <= x <= e_x + arm_l and e_bot - bar_w * 1.5 <= y <= e_bot:
                in_e = True

            # Lettre "C" (droite)
            c_cx = cx + size * 0.06
            c_r_out = size * 0.175
            c_r_in  = size * 0.115
            cdx, cdy = x - c_cx, y - cy
            c_dist = math.sqrt(cdx * cdx + cdy * cdy)

            in_c = False
            if c_r_in <= c_dist <= c_r_out:
                c_angle_deg = math.degrees(math.atan2(cdy, cdx))
                # Ouvrir le C sur la droite (gap entre -45° et +45°)
                if not (-50 <= c_angle_deg <= 50):
                    in_c = True

            if in_e or in_c:
                px = lerp_color(px, text, 0.95)

            row.append(px)
        pixels.append(row)

    return pixels


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "icon_build")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "icon_512.png")

    print("Génération de l'icône 512×512...")
    pixels = draw_icon(512)
    write_png(out, 512, 512, pixels)
    print(f"Icône générée : {out}")
