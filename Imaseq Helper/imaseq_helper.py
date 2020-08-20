"""
WHAT IS IMASEQ HELPER?
Imaseq Helper is a free and open-source extension for Inkscape 1.0, released under the GPLv3 license.
This extension allows you to export PNG images by visibility or layers.
You can also choose to make the extension duplicate a layer base on a setting,
which is a common task when making a frame by frame animation.

HOW IT WORKS?
To make the extension work, you will have to create a layer that has a “rectangle object” in it.
And it has to be a rectangle object, not a circle or rectangle path.
This rectangle object will serve as a selection export area.
Everything visible within the bounds of the rectangle will be exported as a PNG image.
"""
import os
import tempfile
import re
import inkex
from inkex.command import inkscape
from inkex import Layer


class ImaseqHelper(inkex.EffectExtension):
    """Exports a rectangle object along with visible objects/paths"""

    #One inches is 25.4 millimeter
    INCH_IN_MM = 25.4


    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--export_option", default="Visible", help="Determines how to handle exports")
        pars.add_argument("--directory", default=os.path.expanduser("~"), help="Export directory")
        pars.add_argument("--bounds_layer", default="Bounds", help="Layer with rectangle object in it")
        pars.add_argument("--file_name", default="", help="Image file name")
        pars.add_argument("--overwrite", type=inkex.Boolean, help="To overwrite existing files or not")
        pars.add_argument("--dpi", type=float, default=96.00, help="Export size in Dots per inch")
        pars.add_argument("--duplicate_layer", type=inkex.Boolean, help="Create a duplicate layer?")
        pars.add_argument("--layer_opacity", type=float, default=50.0, help="Opacity of the duplicated layer")


    def effect(self):

        if self.options.export_option == "None":
            self.duplicate_current_layer()
            return

        rect_objs = self.get_rect_objs(self.options.bounds_layer)

        if rect_objs is None:
            raise inkex.AbortExtension("Unable to find a layer named \"%s\"." %self.options.bounds_layer)
        if len(rect_objs) == 0:
            raise inkex.AbortExtension("Unable to find a rectangle object in \"%s\" layer." %self.options.bounds_layer)
        if not os.path.isdir(self.options.directory):
            os.makedirs(self.options.directory)
        if self.options.export_option == "All":
            self.export_all_layers(rect_objs, self.options.bounds_layer)
            return

        self.export_visible(rect_objs)
        self.duplicate_current_layer()


    @staticmethod
    def process_file_name(total_rects, file_name, alt_file_name):
        """Process the file name of the image"""
        if not file_name:
            file_name = alt_file_name
        if total_rects > 1:
            file_name = file_name + "-1"

        return file_name


    def export_visible(self, rect_objs):
        """Export whatever is visible within the bounds of the rectagle object"""
        file_name = self.process_file_name(len(rect_objs),
                                           self.options.file_name,
                                           self.svg.get_current_layer().label)
        #Export via for loop just in case their are more than 1 rectangle object found
        for rect in rect_objs:
            self.export_rect(rect, file_name, self.options.overwrite, self.options.input_file)
            file_name = self.update_numeric_suffix(file_name)


    def export_all_layers(self, rect_objs, bounds_layer):
        """Export all layers except bounds layer. Note that this will overwrite files of the same name"""
        cur_layers = self.document.findall(inkex.addNS('g', 'svg'))
        file_name = self.options.file_name
        prev_layer = None

        for layer in cur_layers: #Set all layers to hidden
            if layer.label == bounds_layer:
                continue
            layer.set('style', 'display:none')

        for layer in cur_layers:
            #Exclude bounds layer
            if layer.label == bounds_layer:
                continue
            sub_file_name = self.process_file_name(len(rect_objs), file_name, layer.label)
            #Fail check when prev_layer is still None
            if prev_layer is not None:
                prev_layer.set('style', 'display:none')
            prev_layer = layer
            layer.set('style', 'display:inline')
            #Create a temp file since directly using the current svg won't work
            (_, tmp_svg) = tempfile.mkstemp('.svg')
            with open(tmp_svg, 'wb') as fout:
                fout.write(self.svg.tostring())
            #Export via for loop just in case their are more than 1 rectangle object found
            for rect in rect_objs:
                #Overwrite is set to true
                self.export_rect(rect, sub_file_name, True, tmp_svg)
                sub_file_name = self.update_numeric_suffix(sub_file_name)
            if not file_name:
                continue
            file_name = self.update_numeric_suffix(file_name)


    def get_rect_objs(self, layer_name):
        """Finds the layer base on the UI's layer_name then look for a rectangle object(s)"""
        bounds_layer = None
        #'g' is the default group tag for layers
        layers = self.document.findall(inkex.addNS('g', 'svg'))

        for layer in layers:
            if layer.label == layer_name:
                bounds_layer = layer
                break
        if bounds_layer is not None:
            return bounds_layer.findall(inkex.addNS('rect', "svg"))
        return None


    def export_rect(self, rect, file_name, overwrite, svg_file):
        """Use the rectangle object as export area of the image"""
        (success, kwargs) = self.get_command_kwargs(rect, file_name, overwrite)

        if not success:
            return

        inkscape(svg_file, **kwargs)


    def get_command_kwargs(self, rect, file_name, overwrite):
        """Returns a command kwargs data for image export"""
        rect_id = rect.attrib['id']
        full_path = os.path.join(self.options.directory, "%s.png" %file_name)
        #Rect dimensions are in string millimeters
        export_height = self.get_pixel_length(float(rect.attrib['height']))
        export_width = self.get_pixel_length(float(rect.attrib['width']))

        if overwrite or not os.path.exists(full_path):
            kwargs = {'export-id': rect_id,
                      'export-filename': full_path,
                      'export-height': export_height,
                      'export-width': export_width}
            return (True, kwargs)

        inkex.errormsg("The file already exist on \"%s\"" %full_path)
        return (False, {})


    def get_pixel_length(self, mm_length):
        """Convert millimeter to inches then inches to pixels"""
        return round((mm_length / self.INCH_IN_MM) * self.options.dpi)


    def duplicate_current_layer(self):
        """Duplicates the selected layer if the UI is checked then set its name and opacity"""
        if not self.options.duplicate_layer:
            return

        cur_layer = self.svg.get_current_layer()
        d_layer = Layer.duplicate(cur_layer)
        d_layer.label = self.update_numeric_suffix(cur_layer.label)   
        d_layer_opacity = max(min(self.options.layer_opacity / 100.0, 1.0), 0.0)
        d_layer.style['opacity'] = 1.0
        cur_layer.style['opacity'] = d_layer_opacity


    @staticmethod
    def update_numeric_suffix(string):
        """Add or increment the numberic suffix of the string"""
        if re.search('([0-9]+)$', string) is not None:
            return re.sub('([0-9]+)$',
                          lambda x: str(int(x.group(0)) + 1).zfill(len(x.group(0))),
                          string)
        return string + "-1"


if __name__ == "__main__":
    ImaseqHelper().run()
