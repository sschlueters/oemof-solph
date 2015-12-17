# -*- coding: utf-8 -*-
"""
The module contains linear mixed integer constraints.

@author: Simon Hilpert (simon.hilpert@fh-flensburg.de)
"""
import pyomo.environ as po


def set_bounds(model, block, side="output"):
    """ Set upper and lower bounds via constraints.

    The bounds are set with constraints using the binary status variable
    of the components. The mathematical formulation is as follows:

    If side is `output`:

    .. math::  W(e, O_1(e), t) \\leq out_{max}(e) \\cdot Y(e, t), \
    \\qquad \\forall e, \\forall t

    .. math:: W(e, O_1(e), t) \\geq out_{min}(e) \\cdot Y(e, t), \
    \\qquad \\forall e, \\forall t

    If side is `input`:

    .. math::  W(I(e), e, t) \\leq in_{max}(e) \\cdot Y(e, t), \
    \\qquad \\forall e, \\forall t

    .. math:: W(I(e), e, t) \\geq in_{min}(e) \\cdot Y(e, t), \
    \\qquad \\forall e, \\forall t


    With :math:`e  \\in E` and :math:`E` beeing the set of unique ids for
    all entities grouped inside the attribute `block.objs`.

    :math:`O_1(e)` beeing the set of all first outputs of entitiy
    (component) :math:`e`.

    :math:`I(e)` beeing the set of all inputs of entitiy (component) :math:`e`.

    Parameters
    ----------
    model : OptimizationModel() instance
        An object to be solved containing all Variables, Constraints, Data.
        Bounds are altered at model attributes (variables) of `model`
    block : SimpleBlock()
    side : string
       string to select on which side the bounds should be set
       (`ìnput`, `output`)


    """
    if block.objs is None:
        raise ValueError("No objects defined. Please specify objects for \
                         which bounds should be set.")
    if side == "output":
        out_max = {obj.uid: obj.out_max for obj in block.objs}

        # set upper bounds
        def output_ub_rule(block, e, t):
            lhs = model.w[e, model.O[e][0], t]
            rhs = block.y[e, t] * out_max[e][0]
            return(lhs <= rhs)
        block.maximum_output = po.Constraint(block.indexset,
                                             rule=output_ub_rule)

        out_min = {obj.uid: obj.out_min for obj in block.objs}
        # set lower bounds
        def output_lb_rule(block, e, t):
            lhs = block.y[e, t] * out_min[e][0]
            rhs = model.w[e, model.O[e][0], t]
            return(lhs <= rhs)
        block.minimum_output = po.Constraint(block.indexset,
                                             rule=output_lb_rule)

    if side == "input":
        in_max = {obj.uid: obj.in_max for obj in block.objs}

        # set upper bounds
        def input_ub_rule(block, e, t):
            lhs = model.w[model.I[e], e, t]
            rhs = block.y[e, t] * in_max[e][0]
            return(lhs <= rhs)
        block.maximum_input = po.Constraint(block.indexset, rule=input_ub_rule)

        in_min = {obj.uid: obj.in_min for obj in block.objs}
        # set lower bounds
        def input_lb_rule(block, e, t):
            lhs = block.y[e, t] * in_min[e][0]
            rhs = model.w[model.I[e], e, t]
            return(lhs <= rhs)
        block.minimum_input = po.Constraint(block.indexset, rule=input_lb_rule)

def add_output_gradient_constraints(model, block, grad_direc="both"):
    """ Creates constraints to model the output gradient for milp-models.

    If gradient direction is `positive`:

    .. math:: W(e,O_1(e),t) - W(e,O_1(e),t-1) \\leq gradpos(e) + out_{min}(e) \
    \\cdot (1 - Y(e,t))

    If gradient direction is `negative`:

    .. math:: W(e,O_1(e),t-1) - W(e,O_1(e),t) \\leq gradneg(e) + out_{min}(e) \
    \\cdot (1 - Y(e,t-1))

    With :math:`e  \\in E` and :math:`E` beeing the set of unique ids for
    all entities grouped inside the attribute `block.objs`.

    :math:`O_1(e)` beeing the set of all first outputs of
    entitiy (component) :math:`e`.

    :math:`I(e)` beeing the set of all inputs of entitiy (component) :math:`e`.

    Parameters
    ----------
    model : OptimizationModel() instance
        An object to be solved containing all Variables, Constraints, Data.
    block : SimpleBlock()
    grad_direc : string
         direction of gradient ("both", "positive", "negative")

    References
    ----------
    .. [1] M. Steck (2012): "Entwicklung und Bewertung von Algorithmen zur
       Einsatzplanerstelleung virtueller Kraftwerke", PhD-Thesis,
       TU Munich, p.38
    """
    if block.objs is None:
        raise ValueError("No objects defined. Please specify objects for \
                          which bounds should be set.")

    out_min = {obj.uid: obj.out_min for obj in block.objs}
    grad_pos = {obj.uid: obj.grad_pos for obj in block.objs}

    # TODO: Define correct boundary conditions for t-1 of time
    def grad_pos_rule(block, e, t):
        if t > 1:
            return(model.w[e, model.O[e][0], t] - \
               model.w[e, model.O[e][0], t-1] <=  \
               grad_pos[e] + out_min[e][0] * (1 -block.y[e, t]))
        else:
            return(po.Constraint.Skip)

    grad_neg = {obj.uid: obj.grad_neg for obj in block.objs}
    # TODO: Define correct boundary conditions for t-1 of time horizon
    def grad_neg_rule(block, e, t):
        if t > 1:
            lhs = model.w[e, model.O[e][0], t-1] - model.w[e, model.O[e][0], t]
            rhs =  grad_neg[e] + \
                   out_min[e][0] * (1 -block.y[e, t-1])
            return(lhs <=  rhs)

        else:
            return(po.Constraint.Skip)

    # positive gradient
    if grad_direc == "positive" or grad_direc == "both":
        block.milp_gradient_pos = po.Constraint(block.indexset,
                                                rule=grad_pos_rule)
    # negative gradient
    if grad_direc == "negative" or grad_direc == "both":
        block.milp_gradient_neg = po.Constraint(block.indexset,
                                                rule=grad_neg_rule)


def add_startup_constraints(model, block):
    """ Creates constraints to model the start up of a components.

    The mathematical formulation of constraint is as follows:

    .. math::  Y(e,t) - Yn(e,t-1) \\leq Z_{start}(e,t), \\qquad \
        \\forall e, \\forall t

    With :math:`e  \\in E` and :math:`E` beeing the set of unique ids for
    all entities grouped inside the attribute `block.objs`.


    Parameters
    ----------
    model : OptimizationModel() instance
        An object to be solved containing all Variables, Constraints, Data.
    block : SimpleBlock()

    References
    ----------
    .. [1] M. Steck (2012): "Entwicklung und Bewertung von Algorithmen zur
       Einsatzplanerstelleung virtueller Kraftwerke", PhD-Thesis,
       TU Munich, p.38
    """

    if block.objs is None:
        raise ValueError("No objects defined. Please specify objects for \
                          which constraints should be set.")

    # create binary start-up variables for objects
    block.z_start = po.Var(block.uids, model.timesteps, within=po.Binary)

    def start_up_rule(model, e, t):
        if t >= 1:
            try:
                lhs = block.y[e, t] - block.y[e, t-1] - block.z_start[e, t]
                rhs = 0
                return(lhs <= rhs)
            except:
                raise AttributeError('Constructing startup constraints for' +
                                     ' component with uid: %s went wrong', e)
        else:
            # TODO: Define correct boundary conditions
            return(po.Constraint.Skip)
    block.start_up = po.Constraint(block.indexset, rule=start_up_rule)


def add_shutdown_constraints(model, block):
    """ Creates constraints to model the shut down of a component.

    The mathematical formulation for the constraint is as follows:

    .. math::  Y(e,t-1) - Y(e,t) \\leq Z_{stop}(e,t), \\qquad \
    \\forall e, \\forall t

    With :math:`e  \\in E` and :math:`E` beeing the set of unique ids for
    all entities grouped inside the attribute `block.objs`.

    Parameters
    ----------
    model : OptimizationModel() instance
        An object to be solved containing all Variables, Constraints, Data.
    block : SimpleBlock()

    References
    ----------
    .. [1] M. Steck (2012): "Entwicklung und Bewertung von Algorithmen zur
       Einsatzplanerstelleung virtueller Kraftwerke", PhD-Thesis,
       TU Munich, p.38
    """

    if block.objs is None:
        raise ValueError("No objects defined. Please specify objects for \
                          which constraints should be set.")

    # create binary start-up variables for objects
    block.z_stop = po.Var(block.uids, model.timesteps, within=po.Binary)

    def shutdown_rule(block, e, t):
        if t > 1:
            lhs = block.y[e, t-1] - block.y[e, t] - block.z_stop[e, t]
            rhs = 0
            return(lhs <= rhs)
        else:
            # TODO: Define correct boundary conditions
            return(po.Constraint.Skip)
    block.shut_down = po.Constraint(block.indexset, rule=shutdown_rule)

def add_minimum_downtime(model, block):
    """ Adds minimum downtime constraints for for components grouped inside
    `block.objs`.

    The mathematical formulation for constraints is as follows:

     .. math::  (Y(e, t-1)-Y(e,t)) \\cdot t_{min,off} \\leq t_{min,off} - \
     \\sum_{\\gamma=0}^{t_{min,off}-1} Y(e,t+\\gamma)  \
     \\qquad \\forall e, \\forall t \\in [2, t_{max}-t_{min,off}]

    Extra constraints for last timesteps:

    .. math::  (Y(e, t-1)-Y(e,t)) \\cdot t_{min,off} \\leq t_{min,off} - \
     \\sum_{\\gamma=0}^{t_{max}-t} Y(e,t+\\gamma)  \
     \\qquad \\forall e, \\forall t \\in [t_{max}-t_{min,off}, t_{max}]

    With :math:`e  \\in E` and :math:`E` beeing the set of unique ids for
    all entities grouped inside the attribute `block.objs`.

    Parameters
    ----------
    model : OptimizationModel() instance
        An object to be solved containing all Variables, Constraints, Data.
    block : SimpleBlock()

    """
    if not block.objs or block.objs is None:
        raise ValueError('No objects defined. Please specify objects for' +
                          'which minimum downtime constraints should be set.')

    t_min_off = {obj.uid: obj.t_min_off for obj in block.objs}
    t_max = len(model.timesteps)-1

    def minimum_downtime_rule(block, e, t):
        if t <= 1:
            return po.Constraint.Skip
        elif t >= t_max - t_min_off[e]:
            # Adaption for border sections with range(timesteps_max-t)
            lhs = (block.y[e, t-1] - block.y[e, t]) * t_min_off[e]
            rhs = t_min_off[e] - sum(block.y[e, t + p]
                                     for p in range(t_max - t))
            return(lhs <= rhs)
        else:
            lhs = (block.y[e, t-1] - block.y[e, t]) * t_min_off[e]
            rhs = t_min_off[e] - sum(block.y[e, t + p]
                                     for p in range(t_min_off[e]))
            return(lhs <= rhs)
    block.minimum_downtime = po.Constraint(block.indexset,
                                           rule=minimum_downtime_rule)


def add_minimum_uptime(model, block):
    """ Adds minimum uptime constraints for for components in `block`

    The mathematical formulation for constraints is as follows:

     .. math::  (Y(e,t) - Y(e, t-1)) \\cdot t_{min,on} \\leq  \
     \\sum_{\\gamma=0}^{t_{min,on}-1} Y(e,t+\\gamma)  \
     \\qquad \\forall e, \\forall t \\in [2, t_{max}-t_{min,on}]

     Extra constraint for the last timesteps:

     .. math::  (Y(e,t) - Y(e, t-1)) \\cdot t_{min,on} \\leq  \
      \\sum_{\\gamma=0}^{t_{max}-t} Y(e,t+\\gamma)  \
      \\qquad \\forall e, \\forall t \\in [t_{max}-t_{min,on}, t_{max}]

    With :math:`e  \\in E` and :math:`E` beeing the set of unique ids for
    all entities grouped inside the attribute `block.objs`.

    Parameters
    ----------
    model : OptimizationModel() instance
        An object to be solved containing all Variables, Constraints, Data.
    block : SimpleBlock()

    """
    if not block.objs or block.objs is None:
        raise ValueError('No objects defined. Please specify objects for' +
                          'which minimum uptime constraints should be set.')

    t_min_on = {obj.uid: obj.t_min_on for obj in block.objs}
    t_max = len(model.timesteps)-1

    def minimum_uptime_rule(block, e, t):
        if t <= 1:
            return po.Constraint.Skip
        elif t >= t_max - t_min_on[e]:
            # Adaption for border sections with range(timesteps_max-t)
            lhs = (block.y[e, t] - block.y[e, t-1]) * t_min_on[e]
            rhs = sum(block.y[e, t + p] for p in range(t_max - t))
            return(lhs <= rhs)
        else:
            lhs = (block.y[e, t] - block.y[e, t-1]) * t_min_on[e]
            rhs = sum(block.y[e, t + p] for p in range(t_min_on[e]))
            return(lhs <= rhs)
    block.minimum_uptime = po.Constraint(block.indexset,
                                          rule=minimum_uptime_rule)
