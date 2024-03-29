import json
import logging
import os
import sys
import shutil
import time
import tkinter
from inspect import currentframe, getframeinfo
from tkinter import ttk
from tkinter.filedialog import askopenfilenames
sys.path.append('../..')

import numpy as np

import cv2
from src import tkconfig
from src.image.imcv import ImageCV
from src.image.imnp import ImageNP
from src.support.msg_box import Instruction, MessageBox
from src.support.tkconvert import TkConverter
from src.support.msg_box import MessageBox, Instruction
from src.view.graphcut_app import GraphCutViewer

__FILE__ = os.path.abspath(getframeinfo(currentframe()).filename)
LOGGER = logging.getLogger(__name__)
STATE = ['browse', 'edit']

class GraphCutAction(GraphCutViewer):
    def __init__(self):
        super().__init__()
        self.instruction = None
        self._image_queue = []
        self._current_image_info = {}
        self._current_fl_info = {}
        self._current_fr_info = {}
        self._current_bl_info = {}
        self._current_br_info = {}
        self._current_body_info = {}
        self._current_state = None
        self._tmp_eliminate_track = []
        self._init_instruction()
        
        # color
        self._color_body_line = [0, 0, 255]
        self._color_track_line = [255, 255, 255]
        self._color_eliminate_line = [0, 0, 255]

        # flag
        self._flag_body_width = False
        self._flag_drawing_left = False
        self._flag_drew_left = False
        self._flag_drawing_right = False
        self._flag_drew_right = False
        self._flag_drawing_eliminate = False

        # callback
        self.menu_load_img.add_command(label=u'Import', command=self.input_images)
        self.checkbtn_floodfill.config(command=self._check_and_update_panel_floodfill)
        self.scale_manual_threshold.config(command=self._update_scale_manual_threshold_msg)
        self.scale_gamma.config(command=self._update_scale_gamma_msg)
        for radiobtn in self.radiobtn_threshold_options:
            radiobtn.config(command=self._update_scale_manual_threshold_state)

        # keyboard
        self.root.bind('h', self._k_show_instruction)
        self.root.bind('H', self._k_show_instruction)
        self.root.bind(tkconfig.KEY_UP, self._k_switch_to_previous_image)
        self.root.bind(tkconfig.KEY_LEFT, self._k_switch_to_previous_image)
        self.root.bind(tkconfig.KEY_DOWN, self._k_switch_to_next_image)
        self.root.bind(tkconfig.KEY_RIGHT, self._k_switch_to_next_image)
        self.root.bind(tkconfig.KEY_ESC, lambda x: self._switch_state('browse'))
        self.root.bind(tkconfig.KEY_ENTER, lambda x: self._switch_state('edit'))
        self.scale_gamma.bind(
            tkconfig.MOUSE_RELEASE_LEFT,
            lambda x: self._update_scale_gamma(self.val_scale_gamma.get())
        )
        self.scale_manual_threshold.bind(
            tkconfig.MOUSE_RELEASE_LEFT,
            lambda x: self._update_scale_manual_threshold(self.val_manual_threshold.get())
        )

    @property
    def current_image(self):
        if self._current_image_info and 'path' in self._current_image_info:
            return self._current_image_info['path']
        else:
            return False

    @property
    def flag_was_modified(self):
        flag_option = [self._flag_body_width]
        return any(flag_option)

    # init instruction
    def _init_instruction(self):
        self.instruction = Instruction(title=u'Help menu')
        self.instruction.row_append(u'ESC', u'Browser')
        self.instruction.row_append(u'ENTER', u'Editor')
        self.instruction.row_append(u'UP/LEFT (Browser)', u'Previous img')
        self.instruction.row_append(u'DOWN/RIGHT (Browser)', u'Next img')
        self.instruction.row_append(u'LEFT/RIGHT (Editor)', u'Move symmetric axis 1 pixel')
        self.instruction.row_append(u'PAGE_DOWN/PAGE_UP (Editor)', u'Move symmetric axis 10 pixel')
        self.instruction.row_append(u'SPACE (Editor)', u'Save image and metadata')
        self.instruction.row_append(u'h/H', u'open/close help menu')

    # check and update image to given widget
    def _check_and_update_photo(self, target_widget, photo=None):
        try:
            assert photo is not None
            target_widget.config(image=photo)
        except Exception as e:
            self._default_photo = ImageNP.generate_checkboard((self._im_h, self._im_w), 10)
            self._default_photo = TkConverter.ndarray_to_photo(self._default_photo)
            target_widget.config(image=self._default_photo)

    # check and update image to input panel
    def _check_and_update_panel(self, img=None):
        try:
            assert img is not None
            self.photo_panel = TkConverter.cv2_to_photo(img)
            self._check_and_update_photo(self.label_panel_image, self.photo_panel)
        except Exception as e:
            self._check_and_update_photo(self.label_panel_image, None)

    # check and update panel image with floodfill
    def _check_and_update_panel_floodfill(self):
        if self.val_checkbtn_floodfill.get() == 'on':
            if 'removal' not in self._current_image_info:
                self._current_image_info['removal'] = self._current_image_info['image'].copy()
            self._current_image_info['removal'] = ImageCV.run_floodfill(
                self._current_image_info['removal'],
                threshold=0.85,
                iter_blur=5
            )
        elif self.val_checkbtn_floodfill.get() == 'off':
            self._current_image_info['removal'] = self._current_image_info['image'].copy()
        self.root.focus()

        # check gamma value
        self._update_scale_gamma(self.val_scale_gamma.get())

        # was separate componnent
        if self._current_state == 'edit':
            self._separate_component()

    # check and update panel image by gamma value
    def _check_and_update_panel_by_gamma(self, img=None):
        try:
            assert img is not None
            val_gamma = float(self.val_scale_gamma.get())
            tmp_image = img.copy()
            tmp_image = tmp_image.astype('float64')
            tmp_image[:] /= 255
            tmp_image[:] = tmp_image[:]**val_gamma
            tmp_image[:] *= 255
            tmp_image = tmp_image.astype('uint8')
            self.photo_panel = TkConverter.cv2_to_photo(tmp_image)
            self._current_image_info['preprocess'] = tmp_image
            self._check_and_update_photo(self.label_panel_image, self.photo_panel)

            if self._current_state == 'edit':
                self._render_panel_image()
        except Exception as e:
            LOGGER.exception(e)
            self._check_and_update_photo(self.label_panel_image, None)

    # check and update image to display panel
    def _check_and_update_display(self):
        self.photo_small = ImageNP.generate_checkboard((self._im_h//2, self._im_w//3), 10)
        self.photo_small = TkConverter.ndarray_to_photo(self.photo_small)
        self.photo_large = ImageNP.generate_checkboard((self._im_h, self._im_w//3), 10)
        self.photo_large = TkConverter.ndarray_to_photo(self.photo_large)
        self._check_and_update_fl(None)
        self._check_and_update_fr(None)
        self._check_and_update_bl(None)
        self._check_and_update_br(None)
        self._check_and_update_body(None)

    # check and update image to fl
    def _check_and_update_fl(self, img=None):
        try:
            assert img is None
            self.photo_fl = TkConverter.cv2_to_photo(img)
            self._check_and_update_photo(self.label_fl_image, self.photo_fl)
        except Exception as e:
            self._check_and_update_photo(self.label_fl_image, self.photo_small)

    # check and update image to fr
    def _check_and_update_fr(self, img=None):
        try:
            assert img is None
            self.photo_fr = TkConverter.cv2_to_photo(img)
            self._check_and_update_photo(self.label_fr_image, self.photo_fr)
        except Exception as e:
            self._check_and_update_photo(self.label_fr_image, self.photo_small)

    # check and update image to bl
    def _check_and_update_bl(self, img=None):
        try:
            assert img is None
            self.photo_bl = TkConverter.cv2_to_photo(img)
            self._check_and_update_photo(self.label_bl_image, self.photo_bl)
        except Exception as e:
            self._check_and_update_photo(self.label_bl_image, self.photo_small)

    # check and update image to br
    def _check_and_update_br(self, img=None):
        try:
            assert img is None
            self.photo_br = TkConverter.cv2_to_photo(img)
            self._check_and_update_photo(self.label_br_image, self.photo_br)
        except Exception as e:
            self._check_and_update_photo(self.label_br_image, self.photo_small)

    # check and update image to fr
    def _check_and_update_body(self, img=None):
        try:
            assert img is None
            self.photo_body = TkConverter.cv2_to_photo(img)
            self._check_and_update_photo(self.label_body_image, self.photo_body)
        except Exception as e:
            self._check_and_update_photo(self.label_body_image, self.photo_large)

    # move line to left or right and check boundary
    def _check_and_move_line(self, line, step=0):
        try:
            assert len(line) == 2
            ptx1, ptx2 = line
            assert len(ptx1) == 2 and len(ptx2) == 2
            pty1, pty2 = (ptx1[0]+step, ptx1[1]), (ptx2[0]+step, ptx2[1])
            pty1 = (min(max(0, pty1[0]), self._im_w), pty1[1])
            pty2 = (min(max(0, pty2[0]), self._im_w), pty2[1])
            return (pty1, pty2)
        except Exception as e:
            LOGGER.exception(e)

    # move line to left and update to panel
    def _check_and_update_symmetry(self, step=0):
        if self._flag_body_width:
            LOGGER.info('Got the body width history')
        elif 'symmetry' in self._current_image_info:
            newline = self._check_and_move_line(self._current_image_info['symmetry'], step)
            if not newline:
                LOGGER.error('Failed to move symmetry line')
            else:
                self._current_image_info['symmetry'] = newline
                self._render_panel_image()

    # convert black bg component to rgba transparent bg
    def _convert_to_rgba_component(self, img, mask):
        if mask is None:
            return None
        _mask = mask / 255
        _mask = np.expand_dims(_mask, axis=2)
        _mask = np.concatenate((_mask, _mask, _mask), axis=2)
        image = np.multiply(img, _mask).astype('uint8')
        b, g, r = cv2.split(image)
        return cv2.merge((b, g, r, mask))

    # draw lines by point record
    def _draw_lines_by_points(self, img, track, color=(0, 0, 0)): #Mod 12/12
        for i, record in enumerate(track):
            if len(record) > 2:
                img = self._draw_lines_by_points(img, record, color=color)
            elif i == 0:
                continue
            else:
                cv2.line(img, track[i-1], record, color, 2)
        return img

    # save current image meta
    def _save_image_metadata(self):
        if self._current_state != 'edit':
            LOGGER.warning('Not avaliable to save image metadata in {} state'.format(self._current_state))
        elif not self._current_image_info:
            LOGGER.warning('No image metadata to save')
        else:
            save_meta = {
                'symmetry': None,
                'body_width': None,
                'l_track': None,
                'r_track': None,
                'path': None,
                'size': None,
                'resize':None,
                'timestamp': time.ctime()
            }
            if 'symmetry' in self._current_image_info:
                save_meta['symmetry'] = self._current_image_info['symmetry']
            if 'body_width' in self._current_image_info:
                save_meta['body_width'] = self._current_image_info['body_width']
            if 'l_track' in self._current_image_info:
                save_meta['l_track'] = self._current_image_info['l_track']
            if 'r_track' in self._current_image_info:
                save_meta['r_track'] = self._current_image_info['r_track']
            if 'path' in self._current_image_info:
                save_meta['path'] = self._current_image_info['path']
            if 'size' in self._current_image_info:
                save_meta['size'] = self._current_image_info['size']
            if 'resize' in self._current_image_info:
                save_meta['resize'] = self._current_image_info['resize']

            return save_meta

    # save current omponent meta
    def _save_component_metadata(self, _info):
        if self._current_state != 'edit':
            LOGGER.warning('Not avaliable to save component metadata in {} state'.format(self._current_state))
        elif not isinstance(_info, dict):
            LOGGER.warning('Input _info should be dict')
        elif not _info:
            LOGGER.warning('No component metadata to save')
        else:
            save_meta = {
                'threshold_option': self.val_threshold_option.get(),
                'threshold': None,
                'rect': None,
                'cnts': None
            }
            if 'threshold' in _info and self.val_threshold_option.get() == 'manual':
                save_meta['threshold'] = _info['threshold']
            if 'rect' in _info:
                save_meta['rect'] = _info['rect']
            if 'cnts' in _info:
                save_meta['cnts'] = tuple(i.tolist() if isinstance(i, np.ndarray) else i for i in _info['cnts'])

            return save_meta

    # core function to separate component
    def _separate_component(self):
        if self._current_state != 'edit':
            LOGGER.warning('Not avaliable to separate component in {} state'.format(self._current_state))
        elif 'image' not in self._current_image_info:
            LOGGER.warning('No process image')
        elif not self._flag_body_width:
            LOGGER.warning('Please confirm the body length first')
        elif 'l_track' not in self._current_image_info or 'r_track' not in self._current_image_info:
            LOGGER.warning('No tracking label')
        else:
            # preprocess
            display_image = None
            if self.val_checkbtn_floodfill.get() == 'on' and 'removal' in self._current_image_info:
                display_image = self._current_image_info['removal'].copy()
            else:
                display_image = self._current_image_info['image'].copy()
            display_image = self._separate_component_by_track(display_image)
            display_image = self._separate_component_by_eliminate(display_image)
            display_image = self._separate_component_by_line(display_image)
            display_fl = self._separate_component_by_coor(display_image.copy(), 'fl')
            display_fr = self._separate_component_by_coor(display_image.copy(), 'fr')
            display_bl = self._separate_component_by_coor(display_image.copy(), 'bl')
            display_br = self._separate_component_by_coor(display_image.copy(), 'br')

            # wings mask and get meta - threshold choose by option
            self._current_fl_info = self._separate_component_by_threshold(display_fl)
            self._current_fr_info = self._separate_component_by_threshold(display_fr)
            self._current_bl_info = self._separate_component_by_threshold(display_bl)
            self._current_br_info = self._separate_component_by_threshold(display_br)

            # body mask and get meta - threshold choose by option
            display_body = None
            if self.val_checkbtn_floodfill.get() == 'on' and 'removal' in self._current_image_info:
                display_body = self._current_image_info['removal'].copy()
            else:
                display_body = self._current_image_info['image'].copy()
            display_body = self._separate_component_by_track(display_body)
            display_body[np.where(self._current_fl_info['mask'] == 255)] = 255
            display_body[np.where(self._current_fr_info['mask'] == 255)] = 255
            display_body[np.where(self._current_bl_info['mask'] == 255)] = 255
            display_body[np.where(self._current_br_info['mask'] == 255)] = 255
            self._current_body_info = self._separate_component_by_threshold(display_body)

            # render
            self._check_and_update_fl(self._current_fl_info['show_image'])
            self._check_and_update_fr(self._current_fr_info['show_image'])
            self._check_and_update_bl(self._current_bl_info['show_image'])
            self._check_and_update_br(self._current_br_info['show_image'])
            self._check_and_update_body(self._current_body_info['show_image'])

    # eliminate image by track
    def _separate_component_by_track(self, img):
        if 'image' not in self._current_image_info:
            LOGGER.warning('No process image')
        else:
            if 'l_track' in self._current_image_info:
                self._draw_lines_by_points(img, self._current_image_info['l_track'])
            if 'r_track' in self._current_image_info:
                self._draw_lines_by_points(img, self._current_image_info['r_track'])
            return img

    # eliminate image by eliminate label
    def _separate_component_by_eliminate(self, img):
        if 'image' not in self._current_image_info:
            LOGGER.warning('No process image')
        else:
            if 'eliminate_track' in self._current_image_info:
                self._draw_lines_by_points(img, self._current_image_info['eliminate_track'])
            return img

    # eliminate image by line
    def _separate_component_by_line(self, img):
        if 'image' not in self._current_image_info:
            LOGGER.warning('No process image')
        else:
            if 'l_line' in self._current_image_info:
                self._draw_lines_by_points(img, self._current_image_info['l_line'])
            if 'r_line' in self._current_image_info:
                self._draw_lines_by_points(img, self._current_image_info['r_line'])
            return img

    # removal image background by given x and y and part
    def _separate_component_by_coor(self, img, part, crop=False):
        bottom_y = lambda track: max([ptx[1] for ptx in track])
        top_y = lambda track: min([ptx[1] for ptx in track])
        l_ptx = self._current_image_info['l_line'][0][0]
        r_ptx = self._current_image_info['r_line'][0][0]

        if part == 'fl' and self._current_image_info['l_track']:
            x = l_ptx
            y = bottom_y(self._current_image_info['l_track'])
            img[:, x:] = 0 #Mod 12/12
            img[y:, :] = 0 #Mod 12/12
            if crop:
                img = img[:y, :x]
        elif part == 'fr' and self._current_image_info['r_track']:
            x = r_ptx
            y = bottom_y(self._current_image_info['r_track'])
            img[:, :x] = 0 #Mod 12/12
            img[y:, :] = 0 #Mod 12/12
            if crop:
                img = img[:y, x:]
        elif part == 'bl' and self._current_image_info['l_track']:
            x = l_ptx
            y = top_y(self._current_image_info['l_track'])
            img[:, x:] = 0 #Mod 12/12
            img[:y, :] = 0 #Mod 12/12
            if crop:
                img = img[y:, :x]
        elif part == 'br' and self._current_image_info['r_track']:
            x = r_ptx
            y = top_y(self._current_image_info['r_track'])
            img[:, :x] = 0 #Mod 12/12
            img[:y, :] = 0 #Mod 12/12
            if crop:
                img = img[y:, x:]
        return img

    # get the mask and connected component by threshold option
    def _separate_component_by_threshold(self, img):
        if self.val_threshold_option.get() == 'manual':
            if 'active' not in self.scale_manual_threshold.state():
                LOGGER.error('manual threshold is disable')
            else:
                # preprocess
                save_result = np.zeros(img.shape)
                val_threshold = int(self.val_manual_threshold.get())
                gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                meta = {}

                try:
                    # contour
                    ret, mask = cv2.threshold(gray_img, val_threshold, 255, cv2.THRESH_BINARY) #Mod 12/12

                    cnts = ImageCV.connected_component_by_stats(mask, 1, cv2.CC_STAT_AREA)

                    # filled component
                    fill_mask, cnts = ImageCV.fill_connected_component(img, cnts, threshold=255)
                    target_cnt = ImageNP.contour_to_coor(cnts[0])
                    x, y, w, h = cv2.boundingRect(cnts[0])

                    # image
                    save_result[np.where(fill_mask == 255)] = img[np.where(fill_mask == 255)]
                    save_result = save_result.astype('uint8')
                    show_result = save_result.copy()
                    show_result = show_result[y:y+h, x:x+w]

                    assert 200 < w*h < img.shape[0]*img.shape[1]-200
                    meta = {
                        'threshold': val_threshold,
                        'mask': fill_mask,
                        'cnts': target_cnt,
                        'rect': (x, y, w, h),
                        'save_image': self._convert_to_rgba_component(save_result, fill_mask),
                        'show_image': show_result
                    }
                except Exception as e:
                    meta = {
                        'threshold': None,
                        'mask': None,
                        'cnts': None,
                        'rect': None,
                        'save_image': None,
                        'show_image': None
                    }
                return meta

    # switch to different state
    def _switch_state(self, state):
        '''
        brose mode - switch to previous/next image
        edit mode - computer vision operation
        '''
        if not self._image_queue:
            LOGGER.warn('No images in the image queue')
            self.input_images()

        elif state is None or not state or state not in STATE:
            LOGGER.error('{} not in standard state'.format(state))

        elif state == 'browse':

            # update state message
            self._current_state = 'browse'
            self.label_state.config(text=u'Browser ({}/{}) - {}'.format(
                self._current_image_info['index'] + 1,
                len(self._image_queue),
                os.path.split(self._current_image_info['path'])[1]
            ), style='H2BlackBold.TLabel')

            # update display default photo
            self._check_and_update_display()

            # rebind the keyboard event
            self.root.bind(tkconfig.KEY_UP, self._k_switch_to_previous_image)
            self.root.bind(tkconfig.KEY_LEFT, self._k_switch_to_previous_image)
            self.root.bind(tkconfig.KEY_DOWN, self._k_switch_to_next_image)
            self.root.bind(tkconfig.KEY_RIGHT, self._k_switch_to_next_image)

            # unbind event
            self.root.unbind(tkconfig.KEY_SPACE)

            self._reset_parameter()
            self._check_and_update_panel(img=self._current_image_info['image'])

        elif state == 'edit':

            # update state message
            self._current_state = 'edit'
            self.label_state.config(text=u'Editor ({}/{}) - {}'.format(
                self._current_image_info['index'] + 1,
                len(self._image_queue),
                os.path.split(self._current_image_info['path'])[1]
            ), style='H2RedBold.TLabel')

            # render history
            if self._flag_body_width:
                self._render_panel_image()
            else:
                # generate symmetry line
                self._current_image_info['panel'] = self._current_image_info['image'].copy()
                self._current_image_info['symmetry'] = ImageNP.generate_symmetric_line(self._current_image_info['panel'])
                self._render_panel_image()

                # rebind the keyboard event
                self.root.bind(tkconfig.KEY_LEFT, lambda x: self._check_and_update_symmetry(step=-1))
                self.root.bind(tkconfig.KEY_RIGHT, lambda x: self._check_and_update_symmetry(step=1))
                self.root.bind(tkconfig.KEY_PAGEDOWN, lambda x: self._check_and_update_symmetry(step=-10))
                self.root.bind(tkconfig.KEY_PAGEUP, lambda x: self._check_and_update_symmetry(step=10))
                self.root.bind(tkconfig.KEY_SPACE, self._k_save_all_metadata)

                # bind the mouse event
                self.label_panel_image.bind(tkconfig.MOUSE_MOTION, self._m_check_and_update_body_width)
                self.label_panel_image.bind(tkconfig.MOUSE_RELEASE_LEFT, self._m_confirm_body_width)

    # render panel image
    def _render_panel_image(self):
        if not self._image_queue:
            LOGGER.error('No image in the queue to process')
        elif self._current_state != 'edit':
            LOGGER.error('You cannot render panel image in {} state'.format(self._current_state))
        elif not self._current_image_info or 'panel' not in self._current_image_info:
            LOGGER.error('No processing image to render')
        else:
            if 'preprocess' in self._current_image_info:
                self._current_image_info['panel'] = self._current_image_info['preprocess'].copy()
            else:
                self._current_image_info['panel'] = self._current_image_info['image'].copy()
            if 'symmetry' in self._current_image_info:
                pt1, pt2 = self._current_image_info['symmetry']
                cv2.line(self._current_image_info['panel'], pt1, pt2, [255, 255, 255], 2)
            if 'l_line' in self._current_image_info:
                pt1, pt2 = self._current_image_info['l_line']
                cv2.line(self._current_image_info['panel'], pt1, pt2, self._color_body_line, 2)
            if 'r_line' in self._current_image_info:
                pt1, pt2 = self._current_image_info['r_line']
                cv2.line(self._current_image_info['panel'], pt1, pt2, self._color_body_line, 2)
            if 'l_track' in self._current_image_info:
                self._draw_lines_by_points(
                    img=self._current_image_info['panel'],
                    track=self._current_image_info['l_track'],
                    color=self._color_track_line
                )
            if 'r_track' in self._current_image_info:
                self._draw_lines_by_points(
                    img=self._current_image_info['panel'],
                    track=self._current_image_info['r_track'],
                    color=self._color_track_line
                )
            if 'eliminate_track' in self._current_image_info:
                self._draw_lines_by_points(
                    img=self._current_image_info['panel'],
                    track=self._current_image_info['eliminate_track'],
                    color=self._color_eliminate_line
                )
            if self._tmp_eliminate_track:
                self._draw_lines_by_points(
                    img=self._current_image_info['panel'],
                    track=self._tmp_eliminate_track,
                    color=self._color_eliminate_line
                )

            self._check_and_update_panel(img=self._current_image_info['panel'])

    # reset algorithm parameter
    def _reset_parameter(self):
        # reset color
        self._color_body_line = [0, 0, 255]

        # reset metadata
        self._current_fl_info = {}
        self._current_fr_info = {}
        self._current_bl_info = {}
        self._current_br_info = {}
        self._current_body_info = {}

        # reset flag
        self._flag_body_width = False
        self._flag_drawing_left = False
        self._flag_drew_left = False
        self._flag_drawing_right = False
        self._flag_drew_right = False
        self._flag_drawing_eliminate = False
        self._tmp_eliminate_track = []

        # reset widget
        self.val_checkbtn_floodfill.set('off')
        self.val_scale_gamma.set(0.5) #Mod 12/12
        self.val_threshold_option.set('manual')
        self.val_manual_threshold.set(10) #Mod 12/12

        # unbind mouse event
        self.root.unbind(tkconfig.MOUSE_BUTTON_LEFT)
        self.root.unbind(tkconfig.MOUSE_MOTION_LEFT)
        self.root.unbind(tkconfig.MOUSE_RELEASE_LEFT)

        # update to message widget
        self._update_scale_gamma(self.val_scale_gamma.get())
        self._update_scale_manual_threshold(self.val_manual_threshold.get())

    # update current image
    def _update_current_image(self, index):
        '''
        - record current image index, path
        - read image
        - resize image
        - record current image resize info
        - update size message
        - reset algorithm parameters
        - reset state to browse
        '''
        if self._image_queue is None or not self._image_queue:
            LOGGER.warning('No images in the queue')
        elif index < 0 or index >= len(self._image_queue):
            LOGGER.error('Image queue out of index')
        else:
            self._current_image_info = {
                'index': index,
                'path': self._image_queue[index],
                'image': cv2.imread(self._image_queue[index])
            }
            LOGGER.info('Read image - {}'.format(self._current_image_info['path']))
            self._current_image_info['size'] = self._current_image_info['image'].shape[:2]
            self._current_image_info['image'] = self.auto_resize(self._current_image_info['image'])
            self._current_image_info['resize'] = self._current_image_info['image'].shape[:2]
            self.label_resize.config(text=u'Original size {}X{} -> Current view {}X{}'.format(
                *self._current_image_info['size'][::-1], *self._current_image_info['resize'][::-1]
            ))
            self._im_h, self._im_w = self._current_image_info['resize']
            self._reset_parameter()
            self._switch_state(state='browse')

    # callback: drag the ttk.Scale and show the current value
    def _update_scale_gamma(self, val_gamma):
        # update msg
        val_gamma = float(val_gamma)
        self._update_scale_gamma_msg(val_gamma)

        # update input panel modified process
        if 'removal' not in self._current_image_info:
            self._current_image_info['gamma'] = self._current_image_info['image'].copy()
        else:
            self._current_image_info['gamma'] = self._current_image_info['removal'].copy()

        self._check_and_update_panel_by_gamma(self._current_image_info['gamma'])

    # callback: drag the ttk.Scale and update the message
    def _update_scale_gamma_msg(self, val_gamma):
        # update msg
        val_gamma = float(val_gamma)
        self.label_gamma.config(text=u'Contrast ({:.2f}): '.format(val_gamma))

    # callback: drag the ttk.Scale and show the current value
    def _update_scale_manual_threshold(self, val_threshold):
        # update msg
        val_threshold = float(val_threshold)
        self._update_scale_manual_threshold_msg(val_threshold)
        # update separate component process
        if self._flag_drew_left or self._flag_drew_right:
            self._separate_component()

        

    # callback: drag and update
    def _update_scale_manual_threshold_msg(self, val_threshold):
        # update msg
        val_threshold = float(val_threshold)
        self.label_manual_threshold.config(text=u'Threshold ({:.2f}): '.format(val_threshold))

    # callback: disable the manual scale when the option is not the manual threshold
    def _update_scale_manual_threshold_state(self):
        val_option = self.val_threshold_option.get()
        if val_option == 'manual':
            self.scale_manual_threshold.state(('active', '!disabled'))
        else:
            self.scale_manual_threshold.state(('disabled', '!active'))

    # mouse: check and update body line
    def _m_check_and_update_body_width(self, event=None):
        if self._current_state == 'edit':
            if self._flag_body_width:
                LOGGER.warning('Got body width history')
                self._m_confirm_body_width()
            elif 'symmetry' not in self._current_image_info:
                LOGGER.warning('No symmetry line')
            else:
                middle_line = self._current_image_info['symmetry']
                middle_x = middle_line[0][0]
                body_width = abs(event.x - middle_x)
                l_ptx = max(0, middle_x-body_width)
                r_ptx = min(middle_x+body_width, self._im_w)
                self._current_image_info['l_line'] = ((l_ptx, 0), (l_ptx, self._im_h))
                self._current_image_info['r_line'] = ((r_ptx, 0), (r_ptx, self._im_h))
                self._render_panel_image()

    # mouse: confirm body line and unbind mouse motion
    def _m_confirm_body_width(self, event=None):
        # confirm body width
        self._color_body_line = [255, 0, 0]
        self.label_panel_image.unbind(tkconfig.MOUSE_MOTION)
        self._render_panel_image()
        body_width = abs(event.x-self._current_image_info['symmetry'][0][0])

        # record and set flag
        self._current_image_info['body_width'] = body_width
        self._flag_body_width = True

        # bind the next phase mouse event
        self.label_panel_image.bind(tkconfig.MOUSE_BUTTON_LEFT, self._m_lock_track_flag)
        self.label_panel_image.bind(tkconfig.MOUSE_MOTION_LEFT, self._m_track_separate_label)
        self.label_panel_image.bind(tkconfig.MOUSE_RELEASE_LEFT, self._m_unlock_track_flag)
        self.label_panel_image.bind(tkconfig.MOUSE_BUTTON_RIGHT, self._m_lock_eliminate_flag)
        self.label_panel_image.bind(tkconfig.MOUSE_MOTION_RIGHT, self._m_track_eliminate_label)
        self.label_panel_image.bind(tkconfig.MOUSE_RELEASE_RIGHT, self._m_unlock_eliminate_flag)

        # unbind symmetry line movement
        self.root.unbind(tkconfig.KEY_LEFT)
        self.root.unbind(tkconfig.KEY_RIGHT)

    # mouse: get the track label to separate moth component
    def _m_track_separate_label(self, event=None):
        '''
        Condition of tracking separate label
        e.g. on the left side
        - not was_left and not was_right: mirror
        - not was_left and was_right: reset left and record left
        - was_left and not was_right: reset all and mirror
        - was_left and was_right: reset left and record left
        '''
        if not self._flag_drawing_left and not self._flag_drawing_right:
            LOGGER.debug('Not in the drawing mode')
        else:
            point_x = lambda x: x[0][0]
            mirror_distance = lambda x: abs(x-point_x(self._current_image_info['symmetry']))

            # on the left side
            if self._flag_drawing_left:
                if 0 <= event.x < point_x(self._current_image_info['l_line']):
                    self._current_image_info['l_track'].append((event.x, event.y))
                    if not self._flag_drew_right:
                        self._current_image_info['r_track'].append((event.x+mirror_distance(event.x)*2, event.y))
                else:
                    self._m_unlock_track_flag()

            # on the right side
            if self._flag_drawing_right:
                if point_x(self._current_image_info['r_line']) < event.x <= self._im_w:
                    self._current_image_info['r_track'].append((event.x, event.y))
                    if not self._flag_drew_left:
                        self._current_image_info['l_track'].append((event.x-mirror_distance(event.x)*2, event.y))
                else:
                    self._m_unlock_track_flag()

            if self._flag_drawing_left or self._flag_drawing_right:
                self._render_panel_image()

    # mouse: lock to draw left or right
    def _m_lock_track_flag(self, event=None):
        # check
        if 'l_track' not in self._current_image_info:
            self._current_image_info['l_track'] = []
        if 'r_track' not in self._current_image_info:
            self._current_image_info['r_track'] = []

        # lock and logic operation
        if 'panel' not in self._current_image_info:
            LOGGER.error('No image to process')
        elif self._current_state != 'edit':
            LOGGER.error('Not avaliable to procees in {} state'.format(self._current_state))
        elif not self._flag_body_width:
            LOGGER.error('Please to confirm the body width first')
        elif 0 <= event.x <= self._current_image_info['l_line'][0][0]:
            self._flag_drawing_left = True
            self._flag_drew_left = False
            self._current_image_info['l_track'] = []
            if not self._flag_drew_right:
                self._current_image_info['r_track'] = []
            LOGGER.info('Lock the LEFT flag')
        elif self._current_image_info['r_line'][0][0] <= event.x <= self._im_w:
            self._flag_drawing_right = True
            self._flag_drew_right = False
            self._current_image_info['r_track'] = []
            if not self._flag_drew_left:
                self._current_image_info['l_track'] = []
            LOGGER.info('Lock the RIGHT flag')

    # mouse: unlock to confirm draw left or right
    def _m_unlock_track_flag(self, event=None):
        if not self._flag_drawing_left and not self._flag_drawing_right:
            LOGGER.debug('Not in the drawing mode')
        elif self._flag_drawing_left:
            self._flag_drawing_left = False
            self._flag_drew_left = True
            self._separate_component()
            LOGGER.info('Unlock the LEFT flag')
        elif self._flag_drawing_right:
            self._flag_drawing_right = False
            self._flag_drew_right = True
            self._separate_component()
            LOGGER.info('Unlock the RIGHT flag')

        if self._flag_drawing_left:
            self._flag_drawing_left = False
            LOGGER.warning('Unlock the LEFT flag improperly')
        if self._flag_drawing_right:
            self._flag_drawing_right = False
            LOGGER.warning('Unlock the RIGHT flag improperly')

    # mouse: get the track label to eliminate image
    def _m_track_eliminate_label(self, event=None):
        if self._flag_drawing_eliminate:
            self._tmp_eliminate_track.append((event.x, event.y))
            self._render_panel_image()

    # mouse: lock to draw eliminate label
    def _m_lock_eliminate_flag(self, event=None):
        # lock and logic operation
        if 'panel' not in self._current_image_info:
            LOGGER.error('No image to process')
        elif self._current_state != 'edit':
            LOGGER.error('Not avaliable to procees in {} state'.format(self._current_state))
        elif not self._flag_body_width:
            LOGGER.error('Please to confirm the body width first')
        else:
            self._tmp_eliminate_track = []
            self._flag_drawing_eliminate = True
            LOGGER.info('Lock the ELIMINATE flag')

    # mouse: unlock to draw eliminate label
    def _m_unlock_eliminate_flag(self, eveny=None):
        if self._flag_drawing_eliminate:
            self._flag_drawing_eliminate = False
            if 'eliminate_track' not in self._current_image_info:
                self._current_image_info['eliminate_track'] = []
            if self._tmp_eliminate_track:
                self._current_image_info['eliminate_track'].append(self._tmp_eliminate_track)
            self._tmp_eliminate_track = []
            self._separate_component()
            LOGGER.info('Unlock the ELIMINATE flag')

    # keyboard: save metadata
    def _k_save_all_metadata(self, event=None):
        if self._current_state != 'edit':
            LOGGER.warning('Not avaliable to save metadata in {} state'.format(self._current_state))
        elif 'path' not in self._current_image_info:
            LOGGER.warning('Loss current image path')
        elif (
            not self._current_fl_info and
            not self._current_fr_info and
            not self._current_bl_info and
            not self._current_br_info
        ):
            LOGGER.warning('No component metadata to process')
        else:
            # metadata
            all_metadata = {
                'image': self._save_image_metadata(),
                'fl': self._save_component_metadata(self._current_fl_info),
                'fr': self._save_component_metadata(self._current_fr_info),
                'bl': self._save_component_metadata(self._current_bl_info),
                'br': self._save_component_metadata(self._current_br_info),
                'body': self._save_component_metadata(self._current_body_info)
            }

            # save path
            current_img_path = self._current_image_info['path']
            
            outfolder="segmented"
            save_directory=os.sep.join(current_img_path.split('/')[:-1]+[outfolder])
            #save_directory = os.sep.join(current_img_path.split('.')[:-1])
            sep='_'
            outtemplate=sep.join(current_img_path.split('/')[-1].split('_')[:2])

            if not os.path.exists(save_directory):
                os.makedirs(save_directory)

            save_filename = os.path.join(save_directory, outtemplate+'_metadata.json')
            with open(save_filename, 'w+') as f:
                json.dump(all_metadata, f)
                LOGGER.info('Save metadata - {}'.format(save_filename))

            # Move the finished file to seg-done    
            donefolder="seg_done"
            done_directory=os.sep.join(current_img_path.split('/')[:-1]+[donefolder])
            if not os.path.exists(done_directory):
                os.makedirs(done_directory)
            done_path=os.sep.join(current_img_path.split('/')[:-1]+[donefolder]+[current_img_path.split('/')[-1]])

            shutil.move(current_img_path, done_path)

            
#The images for machine learning will be generated directly from the matlab script for better quality
#             # save image
#             if 'save_image' in self._current_fl_info and self._current_fl_info['save_image'] is not None:
#                 save_imgname = os.path.join(save_directory, outtemplate+'_fore_left.png')
#                 cv2.imwrite(save_imgname, self._current_fl_info['save_image'])
#                 LOGGER.info('Save fore-left component - {}'.format(save_imgname))
#             if 'save_image' in self._current_fr_info and self._current_fr_info['save_image'] is not None:
#                 save_imgname = os.path.join(save_directory, outtemplate+'_fore_right.png')
#                 cv2.imwrite(save_imgname, self._current_fr_info['save_image'])
#                 LOGGER.info('Save fore-right component - {}'.format(save_imgname))
#             if 'save_image' in self._current_bl_info and self._current_bl_info['save_image'] is not None:
#                 save_imgname = os.path.join(save_directory, outtemplate+'_hind_left.png')
#                 cv2.imwrite(save_imgname, self._current_bl_info['save_image'])
#                 LOGGER.info('Save back-left component - {}'.format(save_imgname))
#             if 'save_image' in self._current_br_info and self._current_br_info['save_image'] is not None:
#                 save_imgname = os.path.join(save_directory, outtemplate+'_hind_right.png')
#                 cv2.imwrite(save_imgname, self._current_br_info['save_image'])
#                 LOGGER.info('Save back-right component - {}'.format(save_imgname))
#             if 'save_image' in self._current_body_info and self._current_body_info['save_image'] is not None:
#                 save_imgname = os.path.join(save_directory, outtemplate+'_body.png')
#                 cv2.imwrite(save_imgname, self._current_body_info['save_image'])
#                 LOGGER.info('Save body component - {}'.format(save_imgname))

            self._switch_state('browse')
            self._k_switch_to_next_image()
            Mbox = MessageBox()
            Mbox.info(string=u'All data are exported!')

    # keyboard: show instruction
    def _k_show_instruction(self, event=None):
        if self.instruction is None:
            LOGGER.error('Please init instruction window first')
        else:
            self.instruction.show()

    # keyboard: switch to previous image
    def _k_switch_to_previous_image(self, event=None, step=1):
        if self._current_state is None or self._current_state != 'browse':
            LOGGER.warning('Not in browse mode, cannot switch image')
        elif self.current_image and self.current_image in self._image_queue:
            current_index = self._image_queue.index(self.current_image)
            if current_index == 0:
                LOGGER.warning('Already the first image in the queue')
            elif current_index - step < 0:
                LOGGER.warning('Out of index: current {}, target {}'.format(
                    current_index, current_index - step
                ))
            else:
                target_index = max(0, current_index - step)
                self._update_current_image(index=target_index)
                self._check_and_update_panel(self._current_image_info['image'])
                self._check_and_update_display()
        else:
            LOGGER.warning('No given image')

    # keyboard: switch to next image
    def _k_switch_to_next_image(self, event=None, step=1):
        if self._current_state is None or self._current_state != 'browse':
            LOGGER.warning('Not in browse mode, cannot switch image')
        elif self.current_image and self.current_image in self._image_queue:
            current_index = self._image_queue.index(self.current_image)
            if current_index == len(self._image_queue) - 1:
                LOGGER.warning('Already the last image in the queue')
            elif current_index + step >= len(self._image_queue):
                LOGGER.warning('Out of index: current {}, target {}'.format(
                    current_index, current_index + step
                ))
            else:
                target_index = min(current_index + step,
                                   len(self._image_queue) - 1)
                self._update_current_image(index=target_index)
                self._check_and_update_panel(self._current_image_info['image'])
                self._check_and_update_display()
        else:
            LOGGER.warning('No given image')

    # auto fit the image hight from original image to resize image
    def auto_resize(self, image, ratio=0.6):
        screen_h = self.root.winfo_screenheight()
        screen_w = self.root.winfo_screenwidth()
        image_h, image_w, image_channel = image.shape
        resize_h = screen_h * ratio
        resize_w = (resize_h / image_h) * image_w
        resize_h, resize_w = int(resize_h), int(resize_w)
        image = cv2.resize(image, (resize_w, resize_h),
                           interpolation=cv2.INTER_AREA)
        LOGGER.info('resize image from {}x{} to {}x{}'.format(
            image_w, image_h, int(resize_w), int(resize_h)
        ))
        return image

    # open filedialog to get input image paths
    def input_images(self):
        initdir = os.path.abspath(os.path.join(__FILE__, '../../../'))
        paths = askopenfilenames(
            title=u'Select images',
            filetypes=[('JPG file (*.jpg)', '*jpg'),
                       ('JPEG file (*.jpeg)', '*.jpeg'),
                       ('PNG file (*.png)', '*.png')],
            initialdir=initdir,
            parent=self.root
        )

        if paths:
            self._image_queue = list(paths)

            # update first image to input panel and change display default bg
            self._update_current_image(index=0)
            self._check_and_update_panel(self._current_image_info['image'])
            self._check_and_update_display()

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(filename)12s:L%(lineno)3s [%(levelname)8s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )

    graphcut_action = GraphCutAction()
    graphcut_action.input_images()
    graphcut_action.mainloop()
