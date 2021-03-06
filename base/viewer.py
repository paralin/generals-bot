'''
	@ Harris Christiansen (Harris@HarrisChristiansen.com)
	January 2016
	Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
	Game Viewer
'''

import pygame
import threading
import time

# Color Definitions
BLACK = (0,0,0)
GRAY_DARK = (110,110,110)
GRAY = (160,160,160)
WHITE = (255,255,255)
PLAYER_COLORS = [(255,0,0), (0,0,255), (0,128,0), (128,0,128), (0,128,128), (0,70,0), (128,0,0), (255,165,0), (30,250,30)]

# Table Properies
CELL_WIDTH = 20
CELL_HEIGHT = 20
CELL_MARGIN = 5
SCORES_ROW_HEIGHT = 28
INFO_ROW_HEIGHT = 25

class GeneralsViewer(object):
	def __init__(self, name=None):
		self._name = name
		self._receivedUpdate = False

	def updateGrid(self, update):
		updateDir = dir(update)
		self._map = update
		if "bottomText" in updateDir:
			self._bottomText = update.bottomText
		self._scores = sorted(update.scores, key=lambda general: general['total'], reverse=True) # Sort Scores
		self._receivedUpdate = True
		if "path" in updateDir:
			self._path = [(path.x, path.y) for path in update.path]
		else:
			self._path = []
		if "collect_path" in updateDir:
			self._collect_path = [(path.x, path.y) for path in update.collect_path]
		else:
			self._collect_path = None

	def _initViewier(self):
		pygame.init()

		# Set Window Size
		window_height = self._map.rows * (CELL_HEIGHT + CELL_MARGIN) + CELL_MARGIN + SCORES_ROW_HEIGHT + INFO_ROW_HEIGHT
		window_width = self._map.cols * (CELL_WIDTH + CELL_MARGIN) + CELL_MARGIN
		self._window_size = [window_width, window_height]
		self._screen = pygame.display.set_mode(self._window_size)

		window_title = "Generals IO Bot"
		if (self._name != None):
			window_title += " - " + str(self._name)
		pygame.display.set_caption(window_title)
		self._font = pygame.font.SysFont('Arial', CELL_HEIGHT-10)
		self._fontLrg = pygame.font.SysFont('Arial', CELL_HEIGHT)
		self._bottomText = ""

		self._clock = pygame.time.Clock()

	def mainViewerLoop(self):
		while not self._receivedUpdate: # Wait for first update
			time.sleep(0.5)

		self._initViewier()

		done = False
		while not done:
			for event in pygame.event.get(): # User did something
				if event.type == pygame.QUIT: # User clicked quit
					done = True # Flag done
				elif event.type == pygame.MOUSEBUTTONDOWN: # Mouse Click
					pos = pygame.mouse.get_pos()
					
					# Convert screen to grid coordinates
					column = pos[0] // (CELL_WIDTH + CELL_MARGIN)
					row = pos[1] // (CELL_HEIGHT + CELL_MARGIN)
					
					print("Click ", pos, "Grid coordinates: ", row, column)

			if (self._receivedUpdate):
				self._drawGrid()
				self._receivedUpdate = False

			time.sleep(0.2)

		pygame.quit() # Done. Quit pygame.

	def _drawGrid(self):
		self._screen.fill(BLACK) # Set BG Color

		# Draw Bottom Info Text
		self._screen.blit(self._fontLrg.render("Turn: %d, %s" % (self._map.turn, self._bottomText), True, WHITE), (10, self._window_size[1]-INFO_ROW_HEIGHT))
		
		# Draw Scores
		pos_top = self._window_size[1]-INFO_ROW_HEIGHT-SCORES_ROW_HEIGHT
		score_width = self._window_size[0] / len(self._scores)
		for i, score in enumerate(self._scores):
			score_color = PLAYER_COLORS[int(score['i'])]
			if (score['dead'] == True):
				score_color = GRAY_DARK
			pygame.draw.rect(self._screen, score_color, [score_width*i, pos_top, score_width, SCORES_ROW_HEIGHT])
			self._screen.blit(self._font.render(self._map.usernames[int(score['i'])], True, WHITE), (score_width*i+3, pos_top+1))
			self._screen.blit(self._font.render(str(score['total'])+" on "+str(score['tiles']), True, WHITE), (score_width*i+3, pos_top+1+self._font.get_height()))
	 
		# Draw Grid
		for row in range(self._map.rows):
			for column in range(self._map.cols):
				tile = self._map.grid[row][column]
				# Determine BG Color
				color = WHITE
				color_font = WHITE
				if self._map._tile_grid[row][column] == -2: # Mountain
					color = BLACK
				elif self._map._tile_grid[row][column] == -3: # Fog
					color = GRAY
				elif self._map._tile_grid[row][column] == -4: # Obstacle
					color = GRAY_DARK
				elif self._map._tile_grid[row][column] >= 0: # Player
					color = PLAYER_COLORS[self._map._tile_grid[row][column]]
				else:
					color_font = BLACK

				pos_left = (CELL_MARGIN + CELL_WIDTH) * column + CELL_MARGIN
				pos_top = (CELL_MARGIN + CELL_HEIGHT) * row + CELL_MARGIN
				if (tile in self._map.cities or tile in self._map.generals): # City/General
					# Draw Circle
					pos_left_circle = int(pos_left + (CELL_WIDTH/2))
					pos_top_circle = int(pos_top + (CELL_HEIGHT/2))
					pygame.draw.circle(self._screen, color, [pos_left_circle, pos_top_circle], int(CELL_WIDTH/2))
				else:
					# Draw Rect
					pygame.draw.rect(self._screen, color, [pos_left, pos_top, CELL_WIDTH, CELL_HEIGHT])

				# Draw Text Value
				if (tile.army != 0): # Don't draw on empty tiles
					textVal = str(tile.army)
					self._screen.blit(self._font.render(textVal, True, color_font), (pos_left+2, pos_top+2))

				# Draw Path
				if (self._path != None and (column,row) in self._path):
					self._screen.blit(self._fontLrg.render("*", True, color_font), (pos_left+3, pos_top+3))
				if (self._collect_path != None and (column,row) in self._collect_path):
					self._screen.blit(self._fontLrg.render("*", True, PLAYER_COLORS[8]), (pos_left+6, pos_top+6))
	 
		# Limit to 60 frames per second
		self._clock.tick(60)
 
		# Go ahead and update the screen with what we've drawn.
		pygame.display.flip()

