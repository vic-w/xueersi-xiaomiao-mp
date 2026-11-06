"""小喵掌机国际象棋。

操作：
    方向键：移动棋盘光标
    A：选择棋子或落子
    B：取消选择；未选中棋子时退出

玩家执白，机器执黑。兵升变自动选择皇后。
支持王车易位、吃过路兵、将军、将死、逼和、五十步和棋及基本子力不足和棋。

Sunfish 安装：
    mpremote connect COM9 mip install github:fizban99/micropython-usunfish
"""

import time

from lib.hardware import Speaker

try:
    import sunfish as sunfish_ai
except ImportError:
    sunfish_ai = None


SCREEN_WIDTH = 160
SCREEN_HEIGHT = 128
CELL = 14
BOARD_X = 24
BOARD_Y = 16

COLOR_BLACK = 0x0000
COLOR_WHITE = 0xFFFF
COLOR_LIGHT = 0xD6B5
COLOR_DARK = 0x6B4D
COLOR_YELLOW = 0xFFE0
COLOR_RED = 0xE8A2
COLOR_CYAN = 0x4DFF
COLOR_GREY = 0x8410

START_BOARD = (
    "rnbqkbnr",
    "pppppppp",
    "........",
    "........",
    "........",
    "........",
    "PPPPPPPP",
    "RNBQKBNR",
)

PIECE_VALUES = {
    "P": 100,
    "N": 320,
    "B": 330,
    "R": 500,
    "Q": 900,
    "K": 20000,
}

KNIGHT_STEPS = (
    (-2, -1), (-2, 1), (-1, -2), (-1, 2),
    (1, -2), (1, 2), (2, -1), (2, 1),
)

BISHOP_DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
ROOK_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))
KING_STEPS = BISHOP_DIRECTIONS + ROOK_DIRECTIONS

AI_DEPTH = 2
AI_TIME_LIMIT_MS = 4500
SUNFISH_LEVEL = 2


class ChessGame:
    def __init__(self, ctx):
        self.ctx = ctx
        self.disp = ctx.ed.display
        self.sound = Speaker()
        self.should_exit = False
        self.mode = "ready"
        self.result = ""
        self.sunfish_game = None
        self._reset()

    def _beep(self, frequency, duration):
        try:
            self.sound.beep(frequency, duration)
        except Exception:
            pass

    def _reset(self):
        self.board = []
        for row in START_BOARD:
            for piece in row:
                self.board.append(piece)
        self.side = "w"
        self.castle = [True, True, True, True]
        self.ep_square = None
        self.halfmove = 0
        self.fullmove = 1
        self.cursor_row = 6
        self.cursor_col = 4
        self.selected = None
        self.legal_moves = self._generate_legal_moves()
        self.targets = []
        self.last_move = None
        self.in_check = False
        self.ai_thinking = False
        self.result = ""
        self.mode = "ready"
        self.sunfish_game = None

    def _start(self):
        self._reset()
        if sunfish_ai is None:
            print("Sunfish not installed, using fallback AI")
        if sunfish_ai is not None:
            try:
                sunfish_ai.LEVEL = SUNFISH_LEVEL
                self.sunfish_game = sunfish_ai.game()
                board, _ = next(self.sunfish_game)
                self._sync_sunfish_board(board)
            except Exception as error:
                print("Sunfish init failed:", error)
                self.sunfish_game = None
        self.mode = "playing"
        self._beep(520, 40)

    @staticmethod
    def _is_white(piece):
        return piece != "." and piece.isupper()

    @staticmethod
    def _other(side):
        return "b" if side == "w" else "w"

    def _piece_color_matches(self, piece, side):
        if piece == ".":
            return False
        return piece.isupper() if side == "w" else piece.islower()

    @staticmethod
    def _on_board(row, col):
        return 0 <= row < 8 and 0 <= col < 8

    def _add_move(self, moves, frm, to, promo="", flag=0):
        target = self.board[to]
        if target != "." and target.upper() == "K":
            return
        moves.append((frm, to, promo, flag))

    def _generate_pseudo_moves(self, side):
        moves = []
        for index, piece in enumerate(self.board):
            if not self._piece_color_matches(piece, side):
                continue
            row = index // 8
            col = index % 8
            kind = piece.upper()

            if kind == "P":
                direction = -1 if side == "w" else 1
                start_row = 6 if side == "w" else 1
                promotion_row = 0 if side == "w" else 7
                next_row = row + direction
                if self._on_board(next_row, col):
                    next_index = next_row * 8 + col
                    if self.board[next_index] == ".":
                        if next_row == promotion_row:
                            for promo in ("Q", "R", "B", "N"):
                                self._add_move(moves, index, next_index, promo)
                        else:
                            self._add_move(moves, index, next_index)
                            if row == start_row:
                                double_index = (row + direction * 2) * 8 + col
                                if self.board[double_index] == ".":
                                    self._add_move(moves, index, double_index, "", 3)

                for dc in (-1, 1):
                    target_col = col + dc
                    if not self._on_board(next_row, target_col):
                        continue
                    target_index = next_row * 8 + target_col
                    target = self.board[target_index]
                    if target != "." and not self._piece_color_matches(target, side):
                        if next_row == promotion_row:
                            for promo in ("Q", "R", "B", "N"):
                                self._add_move(moves, index, target_index, promo)
                        else:
                            self._add_move(moves, index, target_index)
                    elif target_index == self.ep_square:
                        self._add_move(moves, index, target_index, "", 1)

            elif kind == "N":
                for dr, dc in KNIGHT_STEPS:
                    nr = row + dr
                    nc = col + dc
                    if self._on_board(nr, nc):
                        target = self.board[nr * 8 + nc]
                        if not self._piece_color_matches(target, side):
                            self._add_move(moves, index, nr * 8 + nc)

            elif kind in ("B", "R", "Q"):
                if kind == "B":
                    directions = BISHOP_DIRECTIONS
                elif kind == "R":
                    directions = ROOK_DIRECTIONS
                else:
                    directions = KING_STEPS
                for dr, dc in directions:
                    nr = row + dr
                    nc = col + dc
                    while self._on_board(nr, nc):
                        target_index = nr * 8 + nc
                        target = self.board[target_index]
                        if target == ".":
                            self._add_move(moves, index, target_index)
                        else:
                            if not self._piece_color_matches(target, side):
                                self._add_move(moves, index, target_index)
                            break
                        nr += dr
                        nc += dc

            elif kind == "K":
                for dr, dc in KING_STEPS:
                    nr = row + dr
                    nc = col + dc
                    if self._on_board(nr, nc):
                        target = self.board[nr * 8 + nc]
                        if not self._piece_color_matches(target, side):
                            self._add_move(moves, index, nr * 8 + nc)

                if side == "w" and index == 60 and not self._is_attacked(60, "b"):
                    if (
                        self.castle[0]
                        and self.board[61] == "."
                        and self.board[62] == "."
                        and not self._is_attacked(61, "b")
                        and not self._is_attacked(62, "b")
                    ):
                        self._add_move(moves, 60, 62, "", 2)
                    if (
                        self.castle[1]
                        and self.board[59] == "."
                        and self.board[58] == "."
                        and self.board[57] == "."
                        and not self._is_attacked(59, "b")
                        and not self._is_attacked(58, "b")
                        and not self._is_attacked(57, "b")
                    ):
                        self._add_move(moves, 60, 58, "", 2)
                elif side == "b" and index == 4 and not self._is_attacked(4, "w"):
                    if (
                        self.castle[2]
                        and self.board[5] == "."
                        and self.board[6] == "."
                        and not self._is_attacked(5, "w")
                        and not self._is_attacked(6, "w")
                    ):
                        self._add_move(moves, 4, 6, "", 2)
                    if (
                        self.castle[3]
                        and self.board[3] == "."
                        and self.board[2] == "."
                        and self.board[1] == "."
                        and not self._is_attacked(3, "w")
                        and not self._is_attacked(2, "w")
                        and not self._is_attacked(1, "w")
                    ):
                        self._add_move(moves, 4, 2, "", 2)
        return moves

    def _find_king(self, side):
        target = "K" if side == "w" else "k"
        for index, piece in enumerate(self.board):
            if piece == target:
                return index
        return -1

    def _is_attacked(self, square, by_side):
        row = square // 8
        col = square % 8

        if by_side == "w":
            for dc in (-1, 1):
                nr = row + 1
                nc = col + dc
                if self._on_board(nr, nc) and self.board[nr * 8 + nc] == "P":
                    return True
        else:
            for dc in (-1, 1):
                nr = row - 1
                nc = col + dc
                if self._on_board(nr, nc) and self.board[nr * 8 + nc] == "p":
                    return True

        knight = "N" if by_side == "w" else "n"
        for dr, dc in KNIGHT_STEPS:
            nr = row + dr
            nc = col + dc
            if self._on_board(nr, nc) and self.board[nr * 8 + nc] == knight:
                return True

        king = "K" if by_side == "w" else "k"
        for dr, dc in KING_STEPS:
            nr = row + dr
            nc = col + dc
            if self._on_board(nr, nc) and self.board[nr * 8 + nc] == king:
                return True

        bishop = "B" if by_side == "w" else "b"
        rook = "R" if by_side == "w" else "r"
        queen = "Q" if by_side == "w" else "q"
        for dr, dc in BISHOP_DIRECTIONS:
            nr = row + dr
            nc = col + dc
            while self._on_board(nr, nc):
                piece = self.board[nr * 8 + nc]
                if piece != ".":
                    if piece == bishop or piece == queen:
                        return True
                    break
                nr += dr
                nc += dc

        for dr, dc in ROOK_DIRECTIONS:
            nr = row + dr
            nc = col + dc
            while self._on_board(nr, nc):
                piece = self.board[nr * 8 + nc]
                if piece != ".":
                    if piece == rook or piece == queen:
                        return True
                    break
                nr += dr
                nc += dc
        return False

    def _in_check(self, side):
        king = self._find_king(side)
        if king < 0:
            return True
        return self._is_attacked(king, self._other(side))

    def _make_move(self, move):
        frm, to, promo, flag = move
        moving_side = self.side
        piece = self.board[frm]
        captured = self.board[to]
        captured_index = to
        rook_from = None
        rook_to = None
        rook_piece = None

        if flag == 1:
            captured_index = to + 8 if moving_side == "w" else to - 8
            captured = self.board[captured_index]
            self.board[captured_index] = "."

        self.board[frm] = "."
        if flag == 2:
            if to > frm:
                rook_from = (frm // 8) * 8 + 7
                rook_to = (frm // 8) * 8 + 5
            else:
                rook_from = (frm // 8) * 8
                rook_to = (frm // 8) * 8 + 3
            rook_piece = self.board[rook_from]
            self.board[rook_from] = "."
            self.board[rook_to] = rook_piece

        if promo:
            self.board[to] = promo if moving_side == "w" else promo.lower()
        else:
            self.board[to] = piece

        old_ep = self.ep_square
        old_castle = self.castle[:]
        old_halfmove = self.halfmove
        self.ep_square = (frm + to) // 2 if flag == 3 else None
        if piece.upper() == "P" or captured != ".":
            self.halfmove = 0
        else:
            self.halfmove += 1

        rights = self.castle[:]
        if frm == 60:
            rights[0] = False
            rights[1] = False
        elif frm == 4:
            rights[2] = False
            rights[3] = False
        for right_index, rook_square in enumerate((63, 56, 7, 0)):
            if frm == rook_square or to == rook_square or captured_index == rook_square:
                rights[right_index] = False
        self.castle = rights

        if moving_side == "w":
            self.side = "b"
        else:
            self.side = "w"
            self.fullmove += 1

        return [
            frm, to, piece, captured, captured_index,
            old_ep, old_castle, old_halfmove, moving_side,
            rook_from, rook_to, rook_piece,
        ]

    def _unmake_move(self, move, undo):
        frm, to, promo, flag = move
        piece = undo[2]
        captured = undo[3]
        captured_index = undo[4]
        self.board[frm] = piece
        if flag == 1:
            self.board[to] = "."
            self.board[captured_index] = captured
        else:
            self.board[to] = captured

        rook_from = undo[9]
        rook_to = undo[10]
        if rook_from is not None:
            self.board[rook_to] = "."
            self.board[rook_from] = undo[11]

        self.ep_square = undo[5]
        self.castle = undo[6]
        self.halfmove = undo[7]
        if undo[8] == "b":
            self.fullmove -= 1
        self.side = undo[8]

    def _generate_legal_moves(self):
        moving_side = self.side
        pseudo = self._generate_pseudo_moves(moving_side)
        legal = []
        for move in pseudo:
            undo = self._make_move(move)
            if not self._in_check(moving_side):
                legal.append(move)
            self._unmake_move(move, undo)
        return legal

    def _insufficient_material(self):
        pieces = []
        bishop_colors = []
        for index, piece in enumerate(self.board):
            if piece == "." or piece.upper() == "K":
                continue
            pieces.append(piece.upper())
            if piece.upper() == "B":
                bishop_colors.append((index // 8 + index % 8) % 2)
        if not pieces:
            return True
        if len(pieces) == 1 and pieces[0] in ("B", "N"):
            return True
        if pieces and all(piece == "B" for piece in pieces):
            return len(set(bishop_colors)) <= 1
        return False

    def _evaluate(self):
        score = 0
        for index, piece in enumerate(self.board):
            if piece == ".":
                continue
            row = index // 8
            col = index % 8
            value = PIECE_VALUES[piece.upper()]
            center = 6 - abs(3.5 - row) - abs(3.5 - col)
            if piece.isupper():
                score += value + center * 2 + (6 - row) * 2
            else:
                score -= value + center * 2 + row * 2
        return score if self.side == "w" else -score

    def _move_order_score(self, move):
        frm, to, promo, flag = move
        score = 0
        captured = self.board[to]
        if flag == 1:
            captured = "P" if self.side == "w" else "p"
        if captured != ".":
            score += PIECE_VALUES[captured.upper()] * 10
        moving = self.board[frm].upper()
        score -= PIECE_VALUES[moving]
        if promo:
            score += PIECE_VALUES[promo]
        return score

    def _ordered_moves(self):
        moves = self._generate_legal_moves()
        moves.sort(key=self._move_order_score, reverse=True)
        return moves

    def _search(self, depth, alpha, beta):
        self.nodes += 1
        if (self.nodes & 63) == 0 and time.ticks_ms() >= self.search_deadline:
            self.search_aborted = True
        if self.search_aborted:
            return self._evaluate()
        if depth <= 0:
            return self._evaluate()

        moves = self._ordered_moves()
        if not moves:
            return -90000 if self._in_check(self.side) else 0

        best = -1000000
        for move in moves:
            undo = self._make_move(move)
            score = -self._search(depth - 1, -beta, -alpha)
            self._unmake_move(move, undo)
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
            if self.search_aborted:
                break
        return best

    def _choose_ai_move(self):
        moves = self._ordered_moves()
        if not moves:
            return None
        self.nodes = 0
        self.search_aborted = False
        self.search_deadline = time.ticks_ms() + AI_TIME_LIMIT_MS
        best_move = moves[0]
        best_score = -1000000
        alpha = -1000000

        for move in moves:
            undo = self._make_move(move)
            score = -self._search(AI_DEPTH - 1, -1000000, -alpha)
            self._unmake_move(move, undo)
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if self.search_aborted:
                break
        return best_move

    def _finish_if_needed(self):
        self.legal_moves = self._generate_legal_moves()
        self.in_check = self._in_check(self.side)
        if not self.legal_moves:
            if self.in_check:
                self.result = "lose" if self.side == "w" else "win"
            else:
                self.result = "draw"
            self.mode = "over"
            return True
        if self.halfmove >= 100 or self._insufficient_material():
            self.result = "draw"
            self.mode = "over"
            return True
        return False

    @staticmethod
    def _move_to_uci(move):
        frm, to, _, _ = move
        frm_row, frm_col = frm // 8, frm % 8
        to_row, to_col = to // 8, to % 8
        return (
            chr(97 + frm_col)
            + str(8 - frm_row)
            + chr(97 + to_col)
            + str(8 - to_row)
        )

    @staticmethod
    def _uci_squares(move):
        frm_col = ord(move[0]) - 97
        frm_row = 8 - int(move[1])
        to_col = ord(move[2]) - 97
        to_row = 8 - int(move[3])
        return frm_row * 8 + frm_col, to_row * 8 + to_col

    def _sync_sunfish_board(self, board):
        if sunfish_ai is None:
            return
        cells = []
        for piece in sunfish_ai.get_board(board):
            cells.append(piece if piece else ".")
        if len(cells) == 64:
            self.board = cells

    def _apply_sunfish_move(self, move_text, board):
        frm, to = self._uci_squares(move_text)
        piece = self.board[frm]
        captured = self.board[to]

        rights = self.castle[:]
        if frm == 4:
            rights[2] = False
            rights[3] = False
        if frm == 0 or to == 0:
            rights[3] = False
        if frm == 7 or to == 7:
            rights[2] = False
        if to == 56:
            rights[1] = False
        if to == 63:
            rights[0] = False
        self.castle = rights

        if piece == "p" and abs(to // 8 - frm // 8) == 2:
            self.ep_square = (frm + to) // 2
        else:
            self.ep_square = None
        if piece == "p" or captured != ".":
            self.halfmove = 0
        else:
            self.halfmove += 1

        self._sync_sunfish_board(board)
        self.side = "w"
        self.fullmove += 1
        self.last_move = (frm, to)
        self.legal_moves = self._generate_legal_moves()
        self.in_check = self._in_check("w")

    def _machine_turn(self):
        self.ai_thinking = True
        self._draw()

        if self.sunfish_game is not None:
            try:
                board, ai_move = next(self.sunfish_game)
            except StopIteration:
                self.ai_thinking = False
                if not self._finish_if_needed():
                    self.result = "win"
                    self.mode = "over"
                return
            except Exception as error:
                print("Sunfish failed, using fallback AI:", error)
                self.sunfish_game = None
            else:
                self.ai_thinking = False
                if ai_move:
                    self._apply_sunfish_move(ai_move, board)
                    self._beep(360, 45)
                self._finish_if_needed()
                return

        move = self._choose_ai_move()
        self.ai_thinking = False
        if move is None:
            self._finish_if_needed()
            return
        self._make_move(move)
        self.last_move = (move[0], move[1])
        self.legal_moves = self._generate_legal_moves()
        self._beep(360, 45)
        self._finish_if_needed()

    def _player_action(self):
        index = self.cursor_row * 8 + self.cursor_col
        piece = self.board[index]

        if self.selected is None:
            if self._piece_color_matches(piece, "w"):
                self.selected = index
                self.targets = [move for move in self.legal_moves if move[0] == index]
                self._beep(620, 25)
            else:
                self._beep(130, 35)
            return

        candidates = [move for move in self.targets if move[1] == index]
        if not candidates:
            if self._piece_color_matches(piece, "w"):
                self.selected = index
                self.targets = [move for move in self.legal_moves if move[0] == index]
                return
            self.selected = None
            self.targets = []
            self._beep(130, 35)
            return

        move = candidates[0]
        if len(candidates) > 1:
            for candidate in candidates:
                if candidate[2] == "Q":
                    move = candidate
                    break

        sunfish_board = None
        if self.sunfish_game is not None:
            try:
                sunfish_board = self.sunfish_game.send(self._move_to_uci(move))
            except Exception as error:
                print("Sunfish rejected game state:", error)
                self.sunfish_game = None
            else:
                if sunfish_board is None:
                    print("Sunfish rejected move, switching to fallback AI")
                    self.sunfish_game = None

        self._make_move(move)
        if sunfish_board is not None:
            self._sync_sunfish_board(sunfish_board)
        self.last_move = (move[0], move[1])
        self.selected = None
        self.targets = []
        self.legal_moves = self._generate_legal_moves()
        self._beep(760, 35)

        if not self._finish_if_needed():
            self._machine_turn()

    def _draw_board(self):
        for row in range(8):
            for col in range(8):
                x = BOARD_X + col * CELL
                y = BOARD_Y + row * CELL
                light = (row + col) % 2 == 0
                color = COLOR_LIGHT if light else COLOR_DARK
                self.disp.fill_rect(x, y, CELL, CELL, color)

        if self.last_move is not None:
            for index in self.last_move:
                row = index // 8
                col = index % 8
                self.disp.rect(
                    BOARD_X + col * CELL,
                    BOARD_Y + row * CELL,
                    CELL,
                    CELL,
                    COLOR_CYAN,
                )

        for target_move in self.targets:
            index = target_move[1]
            row = index // 8
            col = index % 8
            x = BOARD_X + col * CELL + 5
            y = BOARD_Y + row * CELL + 5
            self.disp.fill_rect(x, y, 4, 4, COLOR_CYAN)

        for row in range(8):
            for col in range(8):
                piece = self.board[row * 8 + col]
                if piece == ".":
                    continue
                piece_color = COLOR_WHITE if piece.isupper() else COLOR_BLACK
                piece_background = COLOR_BLACK if piece.isupper() else COLOR_WHITE
                piece_x = BOARD_X + col * CELL + 3
                piece_y = BOARD_Y + row * CELL + 3
                self.disp.fill_rect(piece_x, piece_y, 8, 8, piece_background)
                self.disp.text(
                    piece.upper(),
                    piece_x,
                    piece_y,
                    piece_color,
                )

        if self.selected is not None:
            row = self.selected // 8
            col = self.selected % 8
            self.disp.rect(
                BOARD_X + col * CELL + 2,
                BOARD_Y + row * CELL + 2,
                CELL - 4,
                CELL - 4,
                COLOR_YELLOW,
            )

        x = BOARD_X + self.cursor_col * CELL
        y = BOARD_Y + self.cursor_row * CELL
        self.disp.rect(x, y, CELL, CELL, COLOR_RED)
        self.disp.rect(x + 1, y + 1, CELL - 2, CELL - 2, COLOR_RED)

    def _draw_hud(self):
        self.disp.fill_rect(0, 0, SCREEN_WIDTH, 16, COLOR_BLACK)
        engine_name = "SUNFISH" if self.sunfish_game is not None else "CHESS"
        self.disp.text(engine_name, 2, 4, COLOR_YELLOW)
        if self.result == "win":
            status = "YOU WIN"
        elif self.result == "lose":
            status = "CPU WIN"
        elif self.result == "draw":
            status = "DRAW"
        elif self.ai_thinking:
            status = "CPU..."
        elif self.in_check:
            status = "CHECK"
        elif self.side == "w":
            status = "YOU"
        else:
            status = "CPU"
        self.disp.text(status, SCREEN_WIDTH - len(status) * 8 - 2, 4, COLOR_WHITE)

    def _draw_overlay(self):
        if self.mode == "ready":
            self.disp.fill_rect(24, 40, 112, 56, COLOR_BLACK)
            self.disp.rect(24, 40, 112, 56, COLOR_YELLOW)
            self.disp.text("CHESS", 60, 49, COLOR_YELLOW)
            self.disp.text("YOU: WHITE", 48, 63, COLOR_WHITE)
            self.disp.text("A START", 52, 76, COLOR_CYAN)
            self.disp.text("B EXIT", 56, 86, COLOR_GREY)
        elif self.mode == "over":
            self.disp.fill_rect(18, 39, 124, 58, COLOR_BLACK)
            self.disp.rect(18, 39, 124, 58, COLOR_YELLOW)
            if self.result == "win":
                title = "CHECKMATE!"
            elif self.result == "lose":
                title = "YOU LOSE"
            else:
                title = "DRAW"
            self.disp.text(title, 80 - len(title) * 4, 48, COLOR_YELLOW)
            self.disp.text("A REMATCH", 44, 64, COLOR_WHITE)
            self.disp.text("B EXIT", 56, 78, COLOR_CYAN)

    def _draw(self):
        self.disp.fill(COLOR_BLACK)
        self._draw_board()
        self._draw_hud()
        self._draw_overlay()
        self.disp.show()

    def _read_buttons(self, previous):
        pins = (
            self.ctx.k_u.button,
            self.ctx.k_d.button,
            self.ctx.k_l.button,
            self.ctx.k_r.button,
            self.ctx.k_a.button,
            self.ctx.k_b.button,
        )
        current = [pin.value() == 0 for pin in pins]
        pressed = [current[index] and not previous[index] for index in range(6)]
        return current, pressed

    def play(self):
        buttons = (
            self.ctx.k_u,
            self.ctx.k_d,
            self.ctx.k_l,
            self.ctx.k_r,
            self.ctx.k_a,
            self.ctx.k_b,
        )
        saved = [button.down_func for button in buttons]
        for button in buttons:
            button.down_func = None

        previous = [True] * 6
        last_time = time.ticks_ms()

        try:
            while not self.should_exit:
                now = time.ticks_ms()
                delta = min(0.04, time.ticks_diff(now, last_time) / 1000.0)
                last_time = now

                current, pressed = self._read_buttons(previous)
                if self.mode == "ready":
                    if pressed[4]:
                        self._start()
                    elif pressed[5]:
                        self.should_exit = True
                        break
                elif self.mode == "over":
                    if pressed[4]:
                        self._start()
                    elif pressed[5]:
                        self.should_exit = True
                        break
                else:
                    if pressed[0] and self.cursor_row > 0:
                        self.cursor_row -= 1
                    if pressed[1] and self.cursor_row < 7:
                        self.cursor_row += 1
                    if pressed[2] and self.cursor_col > 0:
                        self.cursor_col -= 1
                    if pressed[3] and self.cursor_col < 7:
                        self.cursor_col += 1
                    if pressed[4]:
                        self._player_action()
                    elif pressed[5]:
                        if self.selected is None:
                            self.should_exit = True
                            break
                        self.selected = None
                        self.targets = []

                previous = current
                self._draw()
                time.sleep_ms(16)
        finally:
            for index, button in enumerate(buttons):
                button.down_func = saved[index]
            try:
                self.sound.pin.deinit()
            except Exception:
                pass


def run(ctx):
    game = ChessGame(ctx)
    game.play()
