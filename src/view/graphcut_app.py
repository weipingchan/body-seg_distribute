import logging
import os
import sys
import tkinter
from tkinter import ttk
sys.path.append('../..')

import cv2
from src.image.imnp import ImageNP
from src.support.tkconvert import TkConverter
from src.view.template import TkViewer
from src.view.tkfonts import TkFonts
from src.view.tkframe import TkFrame, TkLabelFrame
from src.view.ttkstyle import TTKStyle, init_css

LOGGER = logging.getLogger(__name__)

THRESHOLD_OPTION = [(u'Manual', 'manual'), ('Mean Adaptive', 'mean'), ('Gaussian Adaptive', 'gaussian')]

class GraphCutViewer(TkViewer):
    def __init__(self):
        super().__init__()
        self._im_w, self._im_h = 800, 533
        self._init_window(zoom=False)
        self._init_style()
        self._init_frame()
        self._init_menu()

    def _init_style(self):
        init_css()
        theme = 'default'
        if os.name == 'posix':
            theme = 'alt'
        TTKStyle('H4Padding.TLabelframe', theme=theme, background='gray82')
        TTKStyle('H4Padding.TLabelframe.Label', theme=theme,  font=('', 16), background='gray82')
        TTKStyle('H2BlackBold.TLabel', theme=theme, font=('', 24, 'bold'), background='white', foreground='black')
        TTKStyle('H2RedBold.TLabel', theme=theme, font=('', 24, 'bold'), background='white', foreground='red')
        self.font = TkFonts()

    # init frame
    def _init_frame(self):
        # self.root.geometry("1024x600")
        # root
        self.frame_root = TkFrame(self.root, bg='white')
        self.frame_root.grid(row=0, column=0, sticky='news')
        self.set_all_grid_rowconfigure(self.frame_root, 0, 1, 2)
        self.set_all_grid_columnconfigure(self.frame_root, 0)

        # head
        self.frame_head = TkFrame(self.root, bg='white')
        self.frame_head.grid(row=0, column=0, sticky='news')
        self.set_all_grid_rowconfigure(self.frame_head, 0)
        self.set_all_grid_columnconfigure(self.frame_head, 0)

        # body
        self.frame_body = TkFrame(self.frame_root, bg='black')
        self.frame_body.grid(row=1, column=0, sticky='news')
        self.set_all_grid_columnconfigure(self.frame_body, 0, 1)
        self.set_all_grid_rowconfigure(self.frame_body, 0)

        # body > panel
        self.frame_panel = TkFrame(self.root, bg='light pink')
        self.frame_panel.grid(row=0, column=0, sticky='news')
        self.set_all_grid_rowconfigure(self.frame_panel, 0)
        self.set_all_grid_columnconfigure(self.frame_panel, 0)

        # body > display
        self.frame_display = TkFrame(self.frame_body, bg='royal blue')
        self.frame_display.grid(row=0, column=1, sticky='news')
        self.set_all_grid_rowconfigure(self.frame_display, 0)
        self.set_all_grid_columnconfigure(self.frame_display, 0)

        # footer
        self.frame_footer = TkFrame(self.root, bg='gray82')
        self.frame_footer.grid(row=2, column=0, sticky='news')
        self.set_all_grid_rowconfigure(self.frame_footer, 0, 1)
        self.set_all_grid_columnconfigure(self.frame_footer, 0)

        # footer > panel setting
        self.frame_panel_setting = ttk.LabelFrame(self.frame_footer, text=u'Import option: ', style='H4Padding.TLabelframe')
        self.frame_panel_setting.grid(row=0, column=0, sticky='news', pady=10)
        self.set_all_grid_rowconfigure(self.frame_panel_setting, 0, 1)
        self.set_all_grid_columnconfigure(self.frame_panel_setting, 0)

        # footer > panel setting > template option
        self.frame_template_options = TkFrame(self.frame_panel_setting, bg='gray82', pady=5)
        self.frame_template_options.grid(row=0, column=0, sticky='news')

        # footer > panel setting > gamma
        self.frame_gamma = TkFrame(self.frame_panel_setting, bg='gray82', pady=5)
        self.frame_gamma.grid(row=1, column=0, sticky='news')
        self.set_all_grid_rowconfigure(self.frame_gamma, 0)
        self.set_all_grid_columnconfigure(self.frame_gamma, 0)

        # footer > display setting
        self.frame_display_setting = ttk.LabelFrame(self.frame_footer, text=u'Export option: ', style='H4Padding.TLabelframe')
        self.frame_display_setting.grid(row=1, column=0, sticky='news', pady=10)
        self.set_all_grid_rowconfigure(self.frame_display_setting, 0)
        self.set_all_grid_columnconfigure(self.frame_display_setting, 0)

        # temp
        self.temp = TkFrame(self.frame_display_setting, bg='gray82', pady=5)

        # footer > display setting > threshold options
        self.frame_threshold_options = TkFrame(self.temp, bg='gray82', pady=5) # was self.frame_display_setting
        self.frame_threshold_options.grid(row=0, column=0, sticky='news')

        # footer > display setting > manual threshold
        self.frame_manual_threshold = TkFrame(self.temp, bg='gray82', pady=5) # was self.frame_display_setting
        self.frame_manual_threshold.grid(row=1, column=0, sticky='news')
        self.set_all_grid_rowconfigure(self.frame_manual_threshold, 0)
        self.set_all_grid_columnconfigure(self.frame_manual_threshold, 0)

        self._init_widget_head()
        self._init_widget_body()
        self._init_widget_footer()

    # init head widget
    def _init_widget_head(self):
        self.set_all_grid_rowconfigure(self.frame_head, 0, 1)
        self.label_state = ttk.Label(self.frame_panel, text=u'Current Model: N/A', style='H2.TLabel')
        self.label_state.grid(row=0, column=0, sticky='ns')
        self.label_resize = ttk.Label(self.frame_head, text=u'Original Size N/A-> Display Size N/A', style='H2.TLabel')
        self.label_resize.grid(row=1, column=0, sticky='w')

    # init body widget
    def _init_widget_body(self):
        # panel
        self.set_all_grid_rowconfigure(self.frame_panel, 0, 1)
        # self.label_panel = ttk.Label(self.frame_panel, text='Input Panel', style='H2.TLabel')
        # self.label_panel.grid(row=0, column=0, sticky='w')
        self.photo_panel = ImageNP.generate_checkboard((self._im_h, self._im_w), block_size=10)
        self.photo_panel = TkConverter.ndarray_to_photo(self.photo_panel)
        self.label_panel_image = ttk.Label(self.frame_panel, image=self.photo_panel)
        self.label_panel_image.grid(row=1, column=0, sticky='ns')

        # display
        self.label_display = ttk.Label(self.frame_display, text='Display', style='H2.TLabel')
        self.label_display.grid(row=0, column=0, columnspan=3)

        self.set_all_grid_rowconfigure(self.frame_display, 0, 1, 2)
        self.set_all_grid_columnconfigure(self.frame_display, 0, 1, 2)
        self.photo_small = ImageNP.generate_checkboard((self._im_h//2, self._im_w//3), 10)
        self.photo_small = TkConverter.ndarray_to_photo(self.photo_small)
        self.photo_large = ImageNP.generate_checkboard((self._im_h, self._im_w//3), 10)
        self.photo_large = TkConverter.ndarray_to_photo(self.photo_large)
        self.label_fl_image = ttk.Label(self.frame_display, image=self.photo_small)
        self.label_fl_image.grid(row=1, column=0)
        self.label_fr_image = ttk.Label(self.frame_display, image=self.photo_small)
        self.label_fr_image.grid(row=1, column=1)
        self.label_bl_image = ttk.Label(self.frame_display, image=self.photo_small)
        self.label_bl_image.grid(row=2, column=0)
        self.label_br_image = ttk.Label(self.frame_display, image=self.photo_small)
        self.label_br_image.grid(row=2, column=1)
        self.label_body_image = ttk.Label(self.frame_display, image=self.photo_large)
        self.label_body_image.grid(row=1, column=2, rowspan=2)

    # init footer widget
    def _init_widget_footer(self):
        # input panel template option
        self.label_template = ttk.Label(self.frame_template_options, text=u'Filter: ', style='H5.TLabel')
        self.label_template.grid(row=0, column=0, sticky='w')
        self.val_checkbtn_floodfill = tkinter.StringVar()
        self.checkbtn_floodfill = ttk.Checkbutton(
            self.frame_template_options,
            text=u'floodfill',
            variable=self.val_checkbtn_floodfill,
            onvalue='on', offvalue='off',
            style='H5.TCheckbutton'
        )
        self.checkbtn_floodfill.grid(row=0, column=1, sticky='w')

        # input panel gamma
        self.label_gamma = ttk.Label(self.frame_gamma, text=u'Contrast Adjustment ({:.2f}): '.format(1.), style='H5.TLabel')
        self.label_gamma.grid(row=0, column=0, sticky='w')
        self.val_scale_gamma = tkinter.DoubleVar()
        self.val_scale_gamma.set(1.0)
        self.scale_gamma = ttk.Scale(self.frame_gamma,
                                     orient=tkinter.HORIZONTAL,
                                     length=self._im_w*2,
                                     from_=0, to=2.5,
                                     variable=self.val_scale_gamma,
                                     style='Gray.Horizontal.TScale')
        self.scale_gamma.state(('active', '!disabled'))
        self.scale_gamma.grid(row=0, column=1, sticky='w')

        # display threshold option
        self.label_threshold_options = ttk.Label(self.frame_threshold_options, text=u'Threshold Option: ', style='H5.TLabel') 
        self.label_threshold_options.grid(row=0, column=0, sticky='w')
        self.val_threshold_option = tkinter.StringVar()
        self.val_threshold_option.set(THRESHOLD_OPTION[0][-1])
        self.radiobtn_threshold_options = []
        for i, op in enumerate(THRESHOLD_OPTION):
            text, val = op
            radiobtn = ttk.Radiobutton(self.frame_threshold_options,
                                       text=text,
                                       variable=self.val_threshold_option,
                                       value=val,
                                       style='H5.TRadiobutton')
            radiobtn.grid(row=0, column=i+1, sticky='w', padx=10)
            self.radiobtn_threshold_options.append(radiobtn)

        # display threshold manual scale
        self.label_manual_threshold = ttk.Label(self.frame_manual_threshold, text=u'Threshold Value ({:.2f}): '.format(250), style='H5.TLabel')
        self.label_manual_threshold.grid(row=0, column=0, sticky='w')
        self.val_manual_threshold = tkinter.DoubleVar()
        self.val_manual_threshold.set(250)
        self.scale_manual_threshold = ttk.Scale(self.frame_manual_threshold,
                                                orient=tkinter.HORIZONTAL,
                                                length=self._im_w*2,
                                                from_=1, to=254,
                                                variable=self.val_manual_threshold,
                                                style='Gray.Horizontal.TScale')
        self.scale_manual_threshold.state(('active', '!disabled'))
        self.scale_manual_threshold.grid(row=0, column=1, sticky='news', columnspan=len(THRESHOLD_OPTION))

    # init menu bar
    def _init_menu(self):
        # root
        self.menu_root = tkinter.Menu(self.root)
        self.root.config(menu=self.menu_root)

        # load image
        self.menu_load_img = tkinter.Menu(self.menu_root)

        # show menu
        self.menu_root.add_cascade(label=u'File', menu=self.menu_load_img)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(filename)12s:L%(lineno)3s [%(levelname)8s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )

    graphcut_viewer = GraphCutViewer()
    graphcut_viewer.mainloop()
