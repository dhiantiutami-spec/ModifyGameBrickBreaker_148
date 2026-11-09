import array
import math
import random
import pygame

SAMPLE_RATE = 44100
pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
pygame.init()

# ---------- Suara ----------
# Semua efek suara dibuat dari gelombang di kode, jadi tidak perlu file .wav/.mp3
SETTINGS = {"muted": False}


def make_sound(notes, volume=0.35, wave="square"):
    """notes: daftar (frekuensi_awal, frekuensi_akhir, durasi_detik)."""
    samples = array.array("h")
    phase = 0.0
    for f0, f1, dur in notes:
        n = int(SAMPLE_RATE * dur)
        for i in range(n):
            freq = f0 + (f1 - f0) * i / n
            phase += freq / SAMPLE_RATE
            frac = phase % 1.0
            if wave == "square":
                v = 1.0 if frac < 0.5 else -1.0
            elif wave == "triangle":
                v = 4 * abs(frac - 0.5) - 1
            else:
                v = 0.0
            env = (1 - i / n) ** 1.3  # suara memudar di akhir
            samples.append(int(32767 * volume * env * v))
    return pygame.mixer.Sound(buffer=samples.tobytes())


try:
    SOUNDS = {
        "wall": make_sound([(260, 240, 0.05)], 0.25, "triangle"),
        "paddle": make_sound([(330, 300, 0.07)], 0.35, "triangle"),
        "hit": make_sound([(520, 480, 0.06)], 0.25),
        "break": make_sound([(700, 1000, 0.10)], 0.3),
        "launch": make_sound([(300, 700, 0.12)], 0.3),
        "powerup": make_sound([(600, 700, 0.06), (800, 1000, 0.06), (1100, 1300, 0.10)], 0.3),
        "lose": make_sound([(450, 120, 0.45)], 0.35),
        "level": make_sound([(523, 523, 0.10), (659, 659, 0.10), (784, 784, 0.10), (1047, 1047, 0.2)], 0.3),
        "win": make_sound([(523, 523, 0.12), (659, 659, 0.12), (784, 784, 0.12),
                           (1047, 1047, 0.12), (784, 784, 0.10), (1047, 1047, 0.10),
                           (1319, 1319, 0.35)], 0.3),
        "gameover": make_sound([(400, 400, 0.18), (330, 330, 0.18), (260, 260, 0.18), (180, 120, 0.4)], 0.35),
    }
except pygame.error:
    SOUNDS = {}  # tidak ada perangkat audio: game tetap jalan tanpa suara


def play(name):
    if SOUNDS and not SETTINGS["muted"]:
        SOUNDS[name].play()

WIDTH, HEIGHT = 600, 500
FPS = 60
MAX_BALLS = 12  # batas jumlah bola di layar

BLACK = (10, 10, 20)
WHITE = (255, 255, 255)
GRAY = (150, 150, 170)
RED = (230, 70, 70)
GREEN = (80, 220, 120)
BLUE = (80, 150, 255)
YELLOW = (255, 215, 80)
CYAN = (80, 235, 235)

# Warna blok berdasarkan sisa nyawa blok (HP)
HP_COLORS = {1: GREEN, 2: BLUE, 3: RED}

font = pygame.font.Font(None, 24)
big_font = pygame.font.Font(None, 56)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Block Breaker")
clock = pygame.time.Clock()


# Latar belakang berganti tiap level: (warna atas, warna bawah)
THEMES = [
    ((15, 12, 50), (70, 25, 100)),    # ungu malam
    ((5, 40, 65), (10, 115, 125)),    # laut
    ((60, 15, 25), (150, 65, 30)),    # senja
    ((10, 45, 30), (40, 125, 75)),    # hutan
    ((20, 22, 35), (80, 80, 115)),    # baja
]


def make_gradient(top, bottom):
    surf = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.line(surf, color, (0, y), (WIDTH, y))
    return surf.convert()


BACKGROUNDS = [make_gradient(top, bottom) for top, bottom in THEMES]
# bintang: [x, y, kecepatan, ukuran]
STARS = [[random.uniform(0, WIDTH), random.uniform(0, HEIGHT),
          random.uniform(0.2, 0.9), random.choice([1, 1, 2])] for _ in range(60)]


def draw_background(level):
    screen.blit(BACKGROUNDS[(level - 1) % len(BACKGROUNDS)], (0, 0))
    for star in STARS:
        star[1] += star[2]
        if star[1] > HEIGHT:
            star[0], star[1] = random.uniform(0, WIDTH), 0
        shade = int(120 + star[2] * 130)
        pygame.draw.circle(screen, (shade, shade, shade), (int(star[0]), int(star[1])), star[3] // 2 + 1 if star[3] > 1 else 1)


class Paddle:
    BASE_WIDTH = 100

    def __init__(self):
        self.width = self.BASE_WIDTH
        self.height = 14
        self.speed = 8
        self.rect = pygame.Rect(0, HEIGHT - 40, self.width, self.height)
        self.rect.centerx = WIDTH // 2
        self.wide_until = 0

    def update(self, direction, now):
        self.rect.x += direction * self.speed
        self.rect.clamp_ip(screen.get_rect())

        # Power-up "wide" berakhir setelah beberapa detik
        target = self.BASE_WIDTH + (50 if now < self.wide_until else 0)
        if target != self.rect.width:
            cx = self.rect.centerx
            self.rect.width = target
            self.rect.centerx = cx
            self.rect.clamp_ip(screen.get_rect())

    def draw(self):
        pygame.draw.rect(screen, YELLOW if self.rect.width > self.BASE_WIDTH else WHITE,
                         self.rect, border_radius=6)


class Ball:
    RADIUS = 7

    def __init__(self):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.speed = 5.0
        self.stuck = True

    def stick_to(self, paddle):
        self.x = paddle.rect.centerx
        self.y = paddle.rect.top - self.RADIUS - 1
        self.stuck = True

    def launch(self):
        self.vx = random.choice([-1, 1]) * self.speed * 0.5
        self.vy = -self.speed * 0.87
        self.stuck = False

    def set_speed(self, speed):
        """Ubah kecepatan tanpa mengubah arah."""
        length = (self.vx ** 2 + self.vy ** 2) ** 0.5 or 1
        self.speed = speed
        self.vx, self.vy = self.vx / length * speed, self.vy / length * speed

    def spawn_rotated(self, degrees):
        """Buat bola baru dari bola ini dengan arah diputar sekian derajat."""
        b = Ball()
        b.x, b.y, b.speed, b.stuck = self.x, self.y, self.speed, False
        a = math.radians(degrees)
        b.vx = self.vx * math.cos(a) - self.vy * math.sin(a)
        b.vy = self.vx * math.sin(a) + self.vy * math.cos(a)
        return b

    @property
    def rect(self):
        r = self.RADIUS
        return pygame.Rect(self.x - r, self.y - r, r * 2, r * 2)

    def update(self):
        """Return True jika bola jatuh ke bawah."""
        self.x += self.vx
        self.y += self.vy

        if self.x <= self.RADIUS:
            self.x, self.vx = self.RADIUS, abs(self.vx)
            play("wall")
        elif self.x >= WIDTH - self.RADIUS:
            self.x, self.vx = WIDTH - self.RADIUS, -abs(self.vx)
            play("wall")
        if self.y <= self.RADIUS:
            self.y, self.vy = self.RADIUS, abs(self.vy)
            play("wall")

        return self.y > HEIGHT + 20

    def bounce_paddle(self, paddle):
        # Sudut pantulan tergantung di bagian mana paddle terkena bola
        offset = (self.x - paddle.rect.centerx) / (paddle.rect.width / 2)
        offset = max(-0.95, min(0.95, offset))
        self.vx = offset * self.speed
        self.vy = -abs((self.speed ** 2 - self.vx ** 2) ** 0.5)
        self.y = paddle.rect.top - self.RADIUS - 1
        play("paddle")

    def draw(self):
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), self.RADIUS)


class Block:
    def __init__(self, rect, hp):
        self.rect = rect
        self.hp = hp

    def hit(self):
        self.hp -= 1
        return self.hp <= 0

    def draw(self):
        pygame.draw.rect(screen, HP_COLORS[self.hp], self.rect, border_radius=3)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, width=2, border_radius=3)


class PowerUp:
    def __init__(self, center, kind):
        self.rect = pygame.Rect(0, 0, 22, 14)
        self.rect.center = center
        self.kind = kind  # "wide", "life", atau "multi"

    def draw(self):
        color = {"wide": YELLOW, "life": RED, "multi": CYAN}[self.kind]
        text = {"wide": "W", "life": "+", "multi": "x"}[self.kind]
        pygame.draw.rect(screen, color, self.rect, border_radius=7)
        label = font.render(text, True, BLACK)
        screen.blit(label, label.get_rect(center=self.rect.center))


def build_level(level):
    """Semakin tinggi level, semakin banyak blok yang kuat."""
    blocks = []
    cols, rows = 10, min(4 + level, 8)
    gap = 6
    bw = (WIDTH - gap * (cols + 1)) // cols
    bh = 18
    for r in range(rows):
        for c in range(cols):
            if random.random() < 0.08:  # beberapa lubang acak
                continue
            hp = random.choices([1, 2, 3], weights=[6, 3 + level, level])[0]
            x = gap + c * (bw + gap)
            y = 50 + r * (bh + gap)
            blocks.append(Block(pygame.Rect(x, y, bw, bh), hp))
    return blocks


def draw_center_text(text, y, fnt=font, color=WHITE):
    surf = fnt.render(text, True, color)
    screen.blit(surf, surf.get_rect(center=(WIDTH // 2, y)))


def draw_end_panel(title, subtitle, score, high_score, color, hint):
    """Notifikasi di tengah layar untuk game over / menang."""
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 170))
    screen.blit(dim, (0, 0))

    box = pygame.Rect(0, 0, 440, 230)
    box.center = (WIDTH // 2, HEIGHT // 2)
    pygame.draw.rect(screen, (25, 25, 40), box, border_radius=14)
    pygame.draw.rect(screen, color, box, width=3, border_radius=14)

    cx, top = WIDTH // 2, box.top
    draw_center_text(title, top + 45, big_font, color)
    draw_center_text(subtitle, top + 90)
    draw_center_text(f"Skor: {score}     Skor tertinggi: {high_score}", top + 125, color=YELLOW)
    draw_center_text(hint, top + 175, color=GRAY)


def make_ball(level, paddle):
    ball = Ball()
    ball.speed = min(5 + 0.6 * (level - 1), 10)
    ball.stick_to(paddle)
    return ball


def main():
    paddle = Paddle()
    level, lives, score, high_score = 1, 3, 0, 0
    balls = [make_ball(level, paddle)]
    blocks = build_level(level)
    powerups = []
    state = "playing"  # playing | paused | over | won
    running = True

    while running:
        now = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_m:
                    SETTINGS["muted"] = not SETTINGS["muted"]
                elif event.key == pygame.K_p and state in ("playing", "paused"):
                    state = "paused" if state == "playing" else "playing"
                elif event.key == pygame.K_SPACE:
                    if state == "over":
                        level, lives, score = 1, 3, 0
                        blocks = build_level(level)
                        powerups.clear()
                        paddle = Paddle()
                        balls = [make_ball(level, paddle)]
                        state = "playing"
                    elif state == "won":
                        level += 1
                        blocks = build_level(level)
                        powerups.clear()
                        paddle = Paddle()
                        balls = [make_ball(level, paddle)]
                        state = "playing"
                    elif state == "playing" and len(balls) == 1 and balls[0].stuck:
                        balls[0].launch()
                        play("launch")

        waiting = len(balls) == 1 and balls[0].stuck  # bola belum diluncurkan

        if state == "playing":
            keys = pygame.key.get_pressed()
            direction = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - \
                        (keys[pygame.K_LEFT] or keys[pygame.K_a])

            # Kontrol mouse (opsional): geser mouse untuk menggerakkan paddle
            paddle.update(direction, now)
            if pygame.mouse.get_rel() != (0, 0):
                paddle.rect.centerx = pygame.mouse.get_pos()[0]
                paddle.rect.clamp_ip(screen.get_rect())

            if waiting:
                balls[0].stick_to(paddle)
            else:
                for ball in balls[:]:
                    if ball.update():  # bola jatuh
                        balls.remove(ball)
                        continue

                    if ball.vy > 0 and ball.rect.colliderect(paddle.rect):
                        ball.bounce_paddle(paddle)

                    # Tabrakan dengan blok (maks. satu blok per frame per bola)
                    for block in blocks:
                        if ball.rect.colliderect(block.rect):
                            br = ball.rect
                            ox = min(br.right, block.rect.right) - max(br.left, block.rect.left)
                            oy = min(br.bottom, block.rect.bottom) - max(br.top, block.rect.top)
                            if ox < oy:
                                ball.vx *= -1
                            else:
                                ball.vy *= -1

                            if block.hit():
                                play("break")
                                blocks.remove(block)
                                score += 10 * level
                                if random.random() < 0.15:
                                    powerups.append(PowerUp(
                                        block.rect.center,
                                        random.choice(["wide", "life", "multi", "multi", "multi"])))
                            else:
                                play("hit")
                                score += 2
                            break

                # Nyawa berkurang hanya jika SEMUA bola jatuh
                if not balls:
                    lives -= 1
                    if lives <= 0:
                        state = "over"
                        high_score = max(high_score, score)
                        play("gameover")
                    else:
                        play("lose")
                        balls = [make_ball(level, paddle)]

            # Power-up jatuh
            for p in powerups[:]:
                p.rect.y += 3
                if p.rect.colliderect(paddle.rect):
                    play("powerup")
                    if p.kind == "wide":
                        paddle.wide_until = now + 8000
                    elif p.kind == "life":
                        lives = min(lives + 1, 5)
                    elif p.kind == "multi":
                        # Tiap bola yang sedang jalan membelah jadi 3
                        extra = []
                        for b in balls:
                            if not b.stuck:
                                extra += [b.spawn_rotated(20), b.spawn_rotated(-20)]
                        balls.extend(extra[:max(0, MAX_BALLS - len(balls))])
                    powerups.remove(p)
                elif p.rect.top > HEIGHT:
                    powerups.remove(p)

            # Level selesai
            if not blocks:
                score += lives * 50  # bonus sisa nyawa
                high_score = max(high_score, score)
                powerups.clear()
                state = "won"
                play("win")

        # ---------- Render ----------
        draw_background(level)
        for block in blocks:
            block.draw()
        for p in powerups:
            p.draw()
        paddle.draw()
        for ball in balls:
            ball.draw()

        screen.blit(font.render(f"Score: {score}", True, WHITE), (10, 10))
        screen.blit(font.render(f"Level: {level}", True, WHITE), (WIDTH // 2 - 40, 10))
        screen.blit(font.render(f"Lives: {lives}", True, WHITE), (WIDTH - 90, 10))
        if len(balls) > 1:
            screen.blit(font.render(f"Bola: {len(balls)}", True, CYAN), (WIDTH - 90, 28))

        hint = "M: suara " + ("OFF" if SETTINGS["muted"] else "ON")
        screen.blit(font.render(hint, True, GRAY), (10, HEIGHT - 22))

        if state == "playing" and len(balls) == 1 and balls[0].stuck:
            draw_center_text("Tekan SPACE untuk meluncurkan bola", HEIGHT // 2 + 60, color=WHITE)
        elif state == "paused":
            draw_center_text("PAUSE", HEIGHT // 2, big_font)
            draw_center_text("Tekan P untuk lanjut", HEIGHT // 2 + 40, color=WHITE)
        elif state == "won":
            draw_end_panel(
                "KAMU MENANG!",
                f"Level {level} selesai!  Bonus nyawa +{lives * 50}",
                score, high_score, GREEN,
                f"SPACE: lanjut ke level {level + 1}     ESC: keluar")
        elif state == "over":
            draw_end_panel(
                "GAME OVER",
                "Nyawa kamu sudah habis.",
                score, high_score, RED,
                "SPACE: main lagi     ESC: keluar")

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()