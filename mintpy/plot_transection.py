#!/usr/bin/env python3
############################################################
# Program is part of MintPy                                #
# Copyright(c) 2013-2019, Zhang Yunjun, Heresh Fattahi     #
# Author:  Zhang Yunjun, Heresh Fattahi                    #
############################################################


import os
import argparse
import numpy as np
from matplotlib import pyplot as plt, ticker
from mintpy.utils import readfile, utils as ut, plot as pp
from mintpy import view


#####################################################################
# Only one line is supported right now.
GMT_FILE = """GMT xy file, i.e. transect_lonlat.xy:
>\n
131.1663    33.1157
131.2621    33.0860
"""

EXAMPLE = """example:
  plot_transection.py velocity.h5 --start-yx 5290 5579 --end-yx 12177 482
  plot_transection.py velocity.h5 --start-lalo 30.125 129.988 --end-lalo 30.250 130.116
  plot_transection.py velocity.h5 --line-file  transect_lonlat.xy --dem gsi10m.dem

  # profile from multiple files
  plot_transection.py AlosA*/velocity.h5 AlosD*/velocity.h5
"""


def create_parser():
    parser = argparse.ArgumentParser(description='Generate transect/profile along a line',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=EXAMPLE)

    parser.add_argument('file', nargs='+',
                        help='input file to show transection')
    parser.add_argument('--dset', dest='dset', help='Dataset name to read')

    parser.add_argument('--offset','--off', dest='offset', type=float, default=0.05,
                        help='offset between transections from different files. Default: 0.05')

    parser.add_argument('--noverbose', dest='print_msg', action='store_false',
                        help='Disable the verbose message printing.')

    # Start / End Point
    lines = parser.add_argument_group('Start and End Point of Profile')
    lines.add_argument('--start-yx','--yx0', dest='start_yx', metavar=('Y0', 'X0'), type=int, nargs=2,
                       help='start point of the profile in pixel number [y, x]')
    lines.add_argument('--end-yx','--yx1', dest='end_yx', metavar=('Y1', 'X1'), type=int, nargs=2,
                       help='end   point of the profile in pixel number [y, x]')
    lines.add_argument('--start-lalo','--lalo0', dest='start_lalo', metavar=('LAT0', 'LON0'), type=float, nargs=2,
                       help='start point of the profile in [lat, lon]')
    lines.add_argument('--end-lalo','--lalo1', dest='end_lalo', metavar=('LAT1', 'LON1'), type=float, nargs=2,
                       help='end   point of the profile in [lat, lon]')
    lines.add_argument('--line-file', dest='lola_file',
                       help='file with start and end point info in lon lat, same as GMT format.\n'+GMT_FILE)

    parser.add_argument('--interpolation', default='nearest', choices=['nearest', 'bilinear', 'cubic'],
                        help='interpolation method while extacting profile along the line. Default: nearest.')

    lines.add_argument('--ms', '--markersize', dest='marker_size', type=float, default=2.0,
                       help='Point marker size. Default: 2.0')

    parser.add_argument('--view-cmd', dest='view_cmd', default='view.py {} --noverbose ',
                        help='view.py command to plot the input map file\n'+
                             'Default: view.py file --noverbose')

    parser = pp.add_figure_argument(parser)
    parser = pp.add_save_argument(parser)
    return parser


def cmd_line_parse(iargs=None):
    parser = create_parser()
    inps = parser.parse_args(args=iargs)

    if inps.outfile or not inps.disp_fig:
        inps.save_fig = True

    # input file info
    inps.file = ut.get_file_list(inps.file)
    inps.atr = readfile.read_attribute(inps.file[0])
    inps.coord = ut.coordinate(inps.atr)

    # lola_file --> start/end_lalo
    if inps.lola_file:
        inps.start_lalo, inps.end_lalo = read_lonlat_file(inps.lola_file)

    # start/end_lalo --> start/end_yx
    if inps.start_lalo and inps.end_lalo:
        [y0, y1] = inps.coord.lalo2yx([inps.start_lalo[0], inps.end_lalo[0]], coord_type='lat')
        [x0, x1] = inps.coord.lalo2yx([inps.start_lalo[1], inps.end_lalo[1]], coord_type='lon')
        inps.start_yx = [y0, x0]
        inps.end_yx = [y1, x1]

    # verbose print using --noverbose option
    global vprint
    vprint = print if inps.print_msg else lambda *args, **kwargs: None

    if not inps.disp_fig:
        plt.switch_backend('Agg')
    return inps


#####################################################################
def read_lonlat_file(lonlat_file):
    """Read Start/End lat/lon from lonlat text file in gmt format.
    Inputs:
        lonlat_file : text file in gmt lonlat point file
    Outputs:
        start/end_lalo : list of 2 float
    """
    fll = open(lonlat_file, 'r')
    lines = fll.read().splitlines()
    [lon0, lat0] = [float(i) for i in lines[1].split()]
    [lon1, lat1] = [float(i) for i in lines[2].split()]
    fll.close()

    start_lalo = [lat0, lon0]
    end_lalo = [lat1, lon1]
    return start_lalo, end_lalo


#####################################################################
class transectionViewer():
    """class for plot_transection
    Example:
        from mintpy.plot_transection import transectionViewer
        cmd = 'plot_transection.py velocity.h5 --noverbose --start-yx 10 10 --end-yx 200 300'
        obj = transectionViewer(cmd)
        obj.configure()
        obj.plot()
    """

    def __init__(self, cmd=None, iargs=None):
        if cmd:
            iargs = cmd.split()[1:]
        self.cmd = cmd
        self.iargs = iargs

        # figure variables
        self.figname = 'Transection'
        self.fig = None
        self.ax_img = None
        self.ax_txn = None

        self.img = None
        self.line = None
        self.pts_idx = 0
        return

    def configure(self):
        # copy inps to self object
        inps = cmd_line_parse(self.iargs)
        for key, value in inps.__dict__.items():
            setattr(self, key, value)

        # merge inps from view.py into self object
        self.data_img, atr, inps_img = view.prep_slice(self.view_cmd.format(self.file[0]))
        for key, value in inps_img.__dict__.items():
            setattr(self, key, value)
        self.offset *= self.disp_scale

        # keep the following parameter to not affected by merging with view.py
        self.file = inps.file
        self.dset = inps.dset
        self.num_file = len(inps.file)

        # auto figure size
        self.fig_size = inps.fig_size
        if not self.fig_size:
            length, width = int(self.atr['LENGTH']), int(self.atr['WIDTH'])
            fig_size = pp.auto_figure_size((length, width), disp_cbar=True)
            self.fig_size = [fig_size[0]+fig_size[1], fig_size[1]]
        return

    def plot(self):
        # Read data for transection
        self.data_list = []
        self.atr_list = []
        for fname in self.file:
            data, atr = readfile.read(fname, datasetName=self.dset)
            data = pp.scale_data2disp_unit(data, metadata=atr, disp_unit=self.disp_unit)[0]
            self.data_list.append(data)
            self.atr_list.append(atr)        

        # Figure
        self.fig, (self.ax_img, self.ax_txn) = plt.subplots(1, 2, num=self.figname, figsize=self.fig_size)

        # Axes 1 - map with view.prep/plot_slice()
        self.ax_img = view.plot_slice(self.ax_img, self.data_img, self.atr, self)[0]

        # Axes 2 - transection
        self.ax_txn.yaxis.tick_right()
        self.ax_txn.yaxis.set_label_position("right")

        # plot initial input transect
        if self.start_yx and self.end_yx:
            self.draw_line(self.start_yx, self.end_yx)
            self.draw_transection(self.start_yx, self.end_yx)

            # save
            if self.save_fig:
                outfile = '{}.pdf'.format(self.outfile_base)
                self.fig.savefig(outfile, bbox_inches='tight', transparent=True, dpi=inps.fig_dpi)
                vprint('saved transect to', outfile)
        self.fig.subplots_adjust(left=0.05)

        self.cid = self.fig.canvas.mpl_connect('button_release_event', self.select_point)
        if self.disp_fig:
            vprint('showing ...')
            plt.show()
        return

    def draw_line(self, start_yx, end_yx):
        """Draw the transect line in the map axes"""
        # erase existing line
        if self.line is not None:
            self.ax_img.lines.remove(self.line[0])

        # convert coordinates accordingly
        if 'Y_FIRST' in self.atr.keys():
            ys = self.coord.yx2lalo([self.start_yx[0], self.end_yx[0]], coord_type='y')
            xs = self.coord.yx2lalo([self.start_yx[1], self.end_yx[1]], coord_type='x')
        else:
            ys = [start_yx[0], end_yx[0]]
            xs = [start_yx[1], end_yx[1]]

        # plot
        self.line = self.ax_img.plot(xs, ys, 'k--')
        self.fig.canvas.draw()
        return

    def draw_transection(self, start_yx, end_yx):
        """Plot the transect as dots"""
        self.ax_txn.cla()

        # loop for all input files
        for i in range(self.num_file):
            # get transection data
            transect = ut.transect_yx(self.data_list[i],
                                      self.atr_list[i],
                                      start_yx, end_yx,
                                      interpolation=self.interpolation)
            # plot
            self.ax_txn.scatter(transect['distance']/1000.0,
                                transect['value'] - self.offset*i,
                                c=pp.mplColors[i],
                                s=self.marker_size**2)

        self.outfile_base = 'transect_Y{}X{}_Y{}X{}'.format(start_yx[0], start_yx[1], end_yx[0], end_yx[1])

        # title
        msg = 'y/x: ({}, {}) --> ({}, {})'.format(start_yx[0], start_yx[1], end_yx[0], end_yx[1])
        if 'Y_FIRST' in self.atr.keys():
            lat0, lon0 = self.coord.radar2geo(start_yx[0], start_yx[1])[0:2]
            lat1, lon1 = self.coord.radar2geo(end_yx[0], end_yx[1])[0:2]
            msg += '\nlat/lon: ({:.4f}, {:.4f}) --> ({:.4f}, {:.4f})'.format(lat0, lon0, lat1, lon1)
        self.ax_txn.set_title(msg, fontsize=self.font_size)

        # axis format
        self.ax_txn.yaxis.set_minor_locator(ticker.AutoMinorLocator(10))
        self.ax_txn.set_xlabel('Distance (km)', fontsize=self.font_size)
        self.ax_txn.set_ylabel(self.disp_unit, fontsize=self.font_size)
        self.ax_txn.tick_params(which='both', direction='in', labelsize=self.font_size,
                                bottom=True, top=True, left=True, right=True)
        self.ax_txn.set_xlim(0, transect['distance'][-1]/1000.0)
        self.fig.canvas.draw()
        return

    def select_point(self, event):
        """Event handling function for points selection"""
        if event.inaxes == self.ax_img:
            # get row/col number
            if 'Y_FIRST' in self.atr.keys():
                y, x = self.coord.geo2radar(event.ydata, event.xdata, print_msg=False)[0:2]
            else:
                y, x = int(event.ydata+0.5), int(event.xdata+0.5)

            # insert selected points into self.start/end_yx member
            if self.pts_idx == 0:
                self.start_yx = [y, x]
            elif self.pts_idx == 1:
                self.end_yx = [y, x]
            else:
                raise ValueError('number of input points went wrong.')

            # update transection for every two clicks
            self.pts_idx += 1
            if self.pts_idx >= 2:
                self.draw_line(self.start_yx, self.end_yx)
                self.draw_transection(self.start_yx, self.end_yx)
                self.pts_idx = 0
        return


############################ Main ###################################
def main(iargs=None):
    obj = transectionViewer(cmd=iargs)
    obj.configure()
    obj.plot()
    obj.fig.canvas.mpl_disconnect(obj.cid)
    return


#####################################################################
if __name__ == '__main__':
    main()