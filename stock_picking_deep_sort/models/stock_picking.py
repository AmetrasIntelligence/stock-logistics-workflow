import logging

from odoo import api, fields, models

from .res_company import SORTING_DIRECTION

_logger = logging.getLogger(__name__)

string_types = ["char", "text", "date", "datetime", "selection"]


class StockPicking(models.Model):
    _inherit = "stock.picking"

    line_order = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Sort Lines By",
        domain="[('model', '=', 'stock.move')]",
        default=lambda self: self.env.user.company_id.default_stock_move_order,
    )
    line_order_2 = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Sort Lines By",
        domain="[('model', '=', 'stock.move')]",
        default=lambda self: self.env.user.company_id.default_stock_move_order_2,
    )
    line_direction = fields.Selection(
        selection=SORTING_DIRECTION,
        string="Sort Direction",
        default=lambda self: self.env.user.company_id.default_stock_move_direction,
    )

    @api.onchange("line_order", "line_order_2")
    def onchange_line_order(self):
        if not self.line_order and not self.line_order_2:
            self.line_direction = False

    def _sort_stock_move(self):
        def resolve_subfields(obj, line_order):
            if not line_order:
                return None
            val = getattr(obj, line_order.name)
            # Odoo object
            if isinstance(val, models.BaseModel):
                if not val:
                    val = ""
                elif hasattr(val[0], "name"):
                    val = ",".join(val.mapped("name"))
                else:
                    val = ",".join([str(id) for id in val.mapped("id")])
            elif line_order.ttype in string_types:
                if not val:
                    val = ""
                elif not isinstance(val, str):
                    try:
                        val = str(val)
                    except Exception:
                        val = ""
            return val

        if not self.line_order and not self.line_order_2 and not self.line_direction:
            return
        reverse = self.line_direction == "desc"
        sequence = 0
        try:
            sorted_lines = self.move_ids_without_package.sorted(
                key=lambda p: (
                    resolve_subfields(p, self.line_order),
                    resolve_subfields(p, self.line_order_2),
                ),
                reverse=reverse,
            )
            for line in sorted_lines:
                sequence += 10
                if line.sequence == sequence:
                    continue
                line.sequence = sequence
        except Exception:
            _logger.warning("Could not sort purchase order!", exc_info=True)

    def write(self, vals):
        res = super(StockPicking, self).write(vals)
        if (
            "order_line" in vals
            or "line_order" in vals
            or "line_order_2" in vals
            or "line_direction" in vals
        ):
            for record in self:
                record._sort_stock_move()
        return res


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model_create_multi
    def create(self, vals):
        lines = super(StockMove, self).create(vals)
        for order_id in lines.mapped("picking_id"):
            order_id._sort_stock_move()
        return lines
