# backfill IE* with trim, rtrim, ltrim and strip
if not String::trim?
  String::trim = -> @replace /^\s+|\s+$/g, ""
if not String::rtrim?
  String::rtrim = -> @replace /^\s+/, ""
if not String::ltrim?
  String::ltrim = -> @replace /\s+$/, ""
if not String::strip?
  String::strip = -> @replace /^\s+|\s+$/g, ""

TAB = 9
ENTER = 13

filters = [
  { name:'title_case', display:'changes to title case'},
  { name:'capitalize', display:'capitalizes the first letter'},
  { name:'first_word', display:'takes only the first word'}
  { name:'remove_first_word', display:'takes everything after the first word'}
  { name:'upper_case', display:'upper cases all letters'}
  { name:'lower_case', display:'lower cases all letters'}
  { name:'read_digits', display:'reads back a number in a friendly way'}
]

findMatches = (query, data, start, lastIdx, prependChar = undefined) ->

  matched = {}
  results = []

  for option in data
    if option.name.indexOf(query) == 0
      nextDot = option.name.indexOf('.', lastIdx + 1)
      if nextDot == -1

        if prependChar
          name = start + prependChar + option.name
        else
          name = option.name

        display = option.display
      else
        name = ""
        suffix = option.name.substring(lastIdx+1, nextDot)
        if start.length > 0 and start != suffix
          name = start + "."
        name += suffix

        if name.indexOf(query) != 0
          continue

        display = null

      if name not of matched
        matched[name] = name
        results.push({ name: name, display: display })

  return results



@initAtMessageText = (selector, completions=null) ->
  completions = window.message_completions unless completions

  functions = [{"function": "ABS", "arguments": [{"name": "number", "hint": "hint for number"}], "hint": "hint: Returns the absolute value of a number", "description": "Returns the absolute value of a number", "example": "ABS(number)"}, {"function": "AND", "arguments": [{"name": "args", "hint": "hint for args"}], "hint": "hint: Returns TRUE if and only if all its arguments evaluate to TRUE", "description": "Returns TRUE if and only if all its arguments evaluate to TRUE", "example": "AND(args)"}, {"function": "CHAR", "arguments": [{"name": "number", "hint": "hint for number"}], "hint": "hint: Returns the character specified by a number", "description": "Returns the character specified by a number", "example": "CHAR(number)"}, {"function": "CLEAN", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Removes all non-printable characters from a text string", "description": "Removes all non-printable characters from a text string", "example": "CLEAN(text)"}, {"function": "CODE", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Returns a numeric code for the first character in a text string", "description": "Returns a numeric code for the first character in a text string", "example": "CODE(text)"}, {"function": "CONCATENATE", "arguments": [{"name": "args", "hint": "hint for args"}], "hint": "hint: Joins text strings into one text string", "description": "Joins text strings into one text string", "example": "CONCATENATE(args)"}, {"function": "DATE", "arguments": [{"name": "year", "hint": "hint for year"}, {"name": "month", "hint": "hint for month"}, {"name": "day", "hint": "hint for day"}], "hint": "hint: Defines a date value", "description": "Defines a date value", "example": "DATE(year, month, day)"}, {"function": "DATEVALUE", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Converts date stored in text to an actual date", "description": "Converts date stored in text to an actual date", "example": "DATEVALUE(text)"}, {"function": "DAY", "arguments": [{"name": "date", "hint": "hint for date"}], "hint": "hint: Returns only the day of the month of a date (1 to 31)", "description": "Returns only the day of the month of a date (1 to 31)", "example": "DAY(date)"}, {"function": "EDATE", "arguments": [{"name": "date", "hint": "hint for date"}, {"name": "months", "hint": "hint for months"}], "hint": "hint: Moves a date by the given number of months", "description": "Moves a date by the given number of months", "example": "EDATE(date, months)"}, {"function": "FALSE", "arguments": [], "hint": "hint: Returns the logical value FALSE", "description": "Returns the logical value FALSE", "example": "FALSE()"}, {"function": "FIRST_WORD", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Returns the first word in the given text string", "description": "Returns the first word in the given text string", "example": "FIRST_WORD(text)"}, {"function": "FIXED", "arguments": [{"name": "number", "hint": "hint for number"}, {"name": "[decimals]", "hint": "hint for [decimals]"}, {"name": "[no_commas]", "hint": "hint for [no_commas]"}], "hint": "hint: Formats the given number in decimal format using a period and commas", "description": "Formats the given number in decimal format using a period and commas", "example": "FIXED(number, [decimals], [no_commas])"}, {"function": "HOUR", "arguments": [{"name": "datetime", "hint": "hint for datetime"}], "hint": "hint: Returns only the hour of a datetime (0 to 23)", "description": "Returns only the hour of a datetime (0 to 23)", "example": "HOUR(datetime)"}, {"function": "IF", "arguments": [{"name": "logical_test", "hint": "hint for logical_test"}, {"name": "[value_if_true]", "hint": "hint for [value_if_true]"}, {"name": "[value_if_false]", "hint": "hint for [value_if_false]"}], "hint": "hint: Returns one value if the condition evaluates to TRUE, and another value if it evaluates to FALSE", "description": "Returns one value if the condition evaluates to TRUE, and another value if it evaluates to FALSE", "example": "IF(logical_test, [value_if_true], [value_if_false])"}, {"function": "LEFT", "arguments": [{"name": "text", "hint": "hint for text"}, {"name": "num_chars", "hint": "hint for num_chars"}], "hint": "hint: Returns the first characters in a text string", "description": "Returns the first characters in a text string", "example": "LEFT(text, num_chars)"}, {"function": "LEN", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Returns the number of characters in a text string", "description": "Returns the number of characters in a text string", "example": "LEN(text)"}, {"function": "LOWER", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Converts a text string to lowercase", "description": "Converts a text string to lowercase", "example": "LOWER(text)"}, {"function": "MAX", "arguments": [{"name": "args", "hint": "hint for args"}], "hint": "hint: Returns the maximum value of all arguments", "description": "Returns the maximum value of all arguments", "example": "MAX(args)"}, {"function": "MIN", "arguments": [{"name": "args", "hint": "hint for args"}], "hint": "hint: Returns the minimum value of all arguments", "description": "Returns the minimum value of all arguments", "example": "MIN(args)"}, {"function": "MINUTE", "arguments": [{"name": "datetime", "hint": "hint for datetime"}], "hint": "hint: Returns only the minute of a datetime (0 to 59)", "description": "Returns only the minute of a datetime (0 to 59)", "example": "MINUTE(datetime)"}, {"function": "MONTH", "arguments": [{"name": "date", "hint": "hint for date"}], "hint": "hint: Returns only the month of a date (1 to 12)", "description": "Returns only the month of a date (1 to 12)", "example": "MONTH(date)"}, {"function": "NOW", "arguments": [], "hint": "hint: Returns the current date and time", "description": "Returns the current date and time", "example": "NOW()"}, {"function": "OR", "arguments": [{"name": "args", "hint": "hint for args"}], "hint": "hint: Returns TRUE if any argument is TRUE", "description": "Returns TRUE if any argument is TRUE", "example": "OR(args)"}, {"function": "PERCENT", "arguments": [{"name": "number", "hint": "hint for number"}], "hint": "hint: Formats a number as a percentage", "description": "Formats a number as a percentage", "example": "PERCENT(number)"}, {"function": "POWER", "arguments": [{"name": "number", "hint": "hint for number"}, {"name": "power", "hint": "hint for power"}], "hint": "hint: Returns the result of a number raised to a power", "description": "Returns the result of a number raised to a power", "example": "POWER(number, power)"}, {"function": "PROPER", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Capitalizes the first letter of every word in a text string", "description": "Capitalizes the first letter of every word in a text string", "example": "PROPER(text)"}, {"function": "READ_DIGITS", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Formats digits in text for reading in TTS", "description": "Formats digits in text for reading in TTS", "example": "READ_DIGITS(text)"}, {"function": "REMOVE_FIRST_WORD", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Removes the first word from the given text string", "description": "Removes the first word from the given text string", "example": "REMOVE_FIRST_WORD(text)"}, {"function": "REPT", "arguments": [{"name": "text", "hint": "hint for text"}, {"name": "number_times", "hint": "hint for number_times"}], "hint": "hint: Repeats text a given number of times", "description": "Repeats text a given number of times", "example": "REPT(text, number_times)"}, {"function": "RIGHT", "arguments": [{"name": "text", "hint": "hint for text"}, {"name": "num_chars", "hint": "hint for num_chars"}], "hint": "hint: Returns the last characters in a text string", "description": "Returns the last characters in a text string", "example": "RIGHT(text, num_chars)"}, {"function": "SECOND", "arguments": [{"name": "datetime", "hint": "hint for datetime"}], "hint": "hint: Returns only the second of a datetime (0 to 59)", "description": "Returns only the second of a datetime (0 to 59)", "example": "SECOND(datetime)"}, {"function": "SUBSTITUTE", "arguments": [{"name": "text", "hint": "hint for text"}, {"name": "old_text", "hint": "hint for old_text"}, {"name": "new_text", "hint": "hint for new_text"}, {"name": "[instance_num]", "hint": "hint for [instance_num]"}], "hint": "hint: Substitutes new_text for old_text in a text string", "description": "Substitutes new_text for old_text in a text string", "example": "SUBSTITUTE(text, old_text, new_text, [instance_num])"}, {"function": "SUM", "arguments": [{"name": "args", "hint": "hint for args"}], "hint": "hint: Returns the sum of all arguments", "description": "Returns the sum of all arguments", "example": "SUM(args)"}, {"function": "TIME", "arguments": [{"name": "hours", "hint": "hint for hours"}, {"name": "minutes", "hint": "hint for minutes"}, {"name": "seconds", "hint": "hint for seconds"}], "hint": "hint: Defines a time value", "description": "Defines a time value", "example": "TIME(hours, minutes, seconds)"}, {"function": "TIMEVALUE", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Converts time stored in text to an actual time", "description": "Converts time stored in text to an actual time", "example": "TIMEVALUE(text)"}, {"function": "TODAY", "arguments": [], "hint": "hint: Returns the current date", "description": "Returns the current date", "example": "TODAY()"}, {"function": "TRUE", "arguments": [], "hint": "hint: Returns the logical value TRUE", "description": "Returns the logical value TRUE", "example": "TRUE()"}, {"function": "UNICHAR", "arguments": [{"name": "number", "hint": "hint for number"}], "hint": "hint: Returns the unicode character specified by a number", "description": "Returns the unicode character specified by a number", "example": "UNICHAR(number)"}, {"function": "UNICODE", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Returns a numeric code for the first character in a text string", "description": "Returns a numeric code for the first character in a text string", "example": "UNICODE(text)"}, {"function": "UPPER", "arguments": [{"name": "text", "hint": "hint for text"}], "hint": "hint: Converts a text string to uppercase", "description": "Converts a text string to uppercase", "example": "UPPER(text)"}, {"function": "WEEKDAY", "arguments": [{"name": "date", "hint": "hint for date"}], "hint": "hint: Returns the day of the week of a date (1 for Sunday to 7 for Saturday)", "description": "Returns the day of the week of a date (1 for Sunday to 7 for Saturday)", "example": "WEEKDAY(date)"}, {"function": "WORD", "arguments": [{"name": "text", "hint": "hint for text"}, {"name": "number", "hint": "hint for number"}, {"name": "[by_spaces]", "hint": "hint for [by_spaces]"}], "hint": "hint: Extracts the nth word from the given text string", "description": "Extracts the nth word from the given text string", "example": "WORD(text, number, [by_spaces])"}, {"function": "WORD_COUNT", "arguments": [{"name": "text", "hint": "hint for text"}, {"name": "[by_spaces]", "hint": "hint for [by_spaces]"}], "hint": "hint: Returns the number of words in the given text string", "description": "Returns the number of words in the given text string", "example": "WORD_COUNT(text, [by_spaces])"}, {"function": "WORD_SLICE", "arguments": [{"name": "text", "hint": "hint for text"}, {"name": "start", "hint": "hint for start"}, {"name": "[stop]", "hint": "hint for [stop]"}, {"name": "[by_spaces]", "hint": "hint for [by_spaces]"}], "hint": "hint: Extracts a substring spanning from start up to but not-including stop", "description": "Extracts a substring spanning from start up to but not-including stop", "example": "WORD_SLICE(text, start, [stop], [by_spaces])"}, {"function": "YEAR", "arguments": [{"name": "date", "hint": "hint for date"}], "hint": "hint: Returns only the year of a date", "description": "Returns only the year of a date", "example": "YEAR(date)"}];

  variables_completions =
    at: '@'
    escapeChar: '@'
    data: completions
    searchKey: 'name'
    startWithSpace: false
    insertTpl: '@${name}'
    startWithSpace: false
    displayTpl: "<li>${name} <small>${display}</small></li>"
    limit: 200

  functions_completions =
    at: '@('
    escapeChar: '@'
    data: functions
    searchKey: 'function'
    startWithSpace: false
    insertTpl: '@({function})'
    startWithSpace: false
    displayTpl: "<li>${function} <small>${hint}</small></li>"
    limit: 200

  $inputor = $(selector).atwho(variables_completions).atwho(functions_completions)


#  $(selector).atwho
#    at: "@"
#    limit: 15
#    insert_space: false
#    max_len: 100
#    data: completions
###
    callbacks:
      before_insert: (value, item, selectionEvent) ->

        # see if there's more data to filter on
        data = this.settings['@']['data']
        hasMore = false
        for option in data
          if option.name.indexOf(value) == 0 and option.name != value
            hasMore = true
            break

        if selectionEvent.keyCode == TAB and hasMore
          value += '.'
        else
          value += ' '
        return value

      filter: (query, data, search_key) ->

        q = query.toLowerCase()
        lastIdx = q.lastIndexOf('.')
        start = q.substring(0, lastIdx)

        results = findMatches(q, data, start, lastIdx)

        if results.length > 0
          return results

        flag = "@"
        flag = "(?:^|\\s)" + flag.replace(/[\-\[\]\/\{\}\(\)\*\+\?\\\^\$\|]/g, "\\$&")
        regexp = new RegExp("([A-Za-z0-9_+-.]*\\|)([A-Za-z0-9_+-.]*)", "gi")
        match = regexp.exec(q)

        if match

          # check that we should even be matching
          name = q.substring(0, q.indexOf('|'))
          found = false
          for d in data
            if d.name == name
              found = true
              break

          if not found
            return results

          filterQuery = match[2]
          lastIdx = q.lastIndexOf('|') + 1
          start = q.substring(0, lastIdx - 1)
          filterQuery = q.substring(lastIdx)
          results = findMatches(filterQuery, filters, start , q.lastIndexOf('|'), '|')

        return results


      tpl_eval: (tpl, map) ->

        if not map.display
          tpl = "<li data-value='${name}'>${name}</li>"
        try
          return tpl.replace /\$\{([^\}]*)\}/g, (tag, key, pos) -> map[key]
        catch error
          return ""

      highlighter: (li, query) ->
        return li

      
      ###
###
      matcher: (flag, subtext) ->
        flag = "(?:^|\\s)" + flag.replace(/[\-\[\]\/\{\}\(\)\*\+\?\\\^\$\|]/g, "\\$&")
        regexp = new RegExp(flag + "([A-Za-z0-9_+-.\\|]*)$|" + flag + "([^\\x00-\\xff]*)$", "gi")
        match = regexp.exec(subtext)
        if match
          match[2] or match[1]
        else
          null
       ###
###
    tpl: "<li data-value='${name}'>${name} (<span>${display}</span>)</li>"
###




@useFontCheckbox = (selector, displayLabel=false) ->

  checkboxes = $(selector)

  checkboxes.each ->
    input = $(this)
    controlGroup = input.parents('.form-group')
    label = controlGroup.children("label").text()
    help = input.parent().children(".help-block")

    html = "<div class='form-group font-checkbox'>"
    html += "<label"
    if !displayLabel
      html += " id='checkbox-label'"
    html += " class='control-label' for='"
    html += input.prop('id')
    html += "'>"
    html += label
    html += "</label>"
    html += "<div class='controls field-input"
    if input.prop('checked')
      html += " checked"
    html += "'>"
    html += "<div class='hidden-input hide'>"
    html += "<input name='" + input.prop('name') + "' id='" + input.prop('id') + "' type='" + input.prop('type') + "' "
    if input.prop('checked')
      html += " checked"
    html += "/>"
    html += "</div>"
    html += "<div class='glyph notif-checkbox'></div><div></div>"
    if help
      if !displayLabel
        html += "<div class='help-block'><label for='"
        html += input.prop('id')
        html += "'>" + help.text() + "</label></div>"
      else
        html += "<p class='help-block'>" + help.text() + "</p>"
    html += "</div></div>"

    controlGroup.replaceWith(html)

  ele = $(".font-checkbox")

  glyphCheck = ele.children('.controls').children('.glyph.notif-checkbox')
  glyphCheck.on 'click', ->
    cell = $(this).parent('.field-input')
    ipt = cell.children().children("input[type='checkbox']")

    if ipt.prop('checked')
      cell.removeClass 'checked'
      ipt.prop('checked', false)
    else
      cell.addClass 'checked'
      ipt.prop('checked', true)

  chkBox = ele.find("input[type=checkbox]")
  chkBox.on 'change', ->
    cell = ele.find('.field-input')

    if $(this).prop('checked')
      cell.addClass 'checked'
    else
      cell.removeClass 'checked'


@select2div = (selector, width="350px", placeholder=null, add_prefix=null) ->
  ele = $(selector)
  children = ele.children('option')
  options = []
  selected = null
  for child in children
    option = { id: child.value, text: child.label }
    if child.selected
      selected = option
    options.push(option)

  ele.replaceWith("<input width='" + width + "' name='" + ele.attr('name') + "' style='width:" + width + "' id='" + ele.attr('id') + "'/>")
  ele = $(selector)

  if add_prefix
    ele.select2
      name: name
      data: options
      placeholder: placeholder
      query: (query) ->
        data = { results: [] }
        for d in this['data']
          if d.text.toLowerCase().indexOf(query.term.toLowerCase().strip()) != -1
            data.results.push({ id:d.id, text: d.text });
        if data.results.length == 0 and query.term.strip().length > 0
          data.results.push({id:'[_NEW_]' + query.term, text: add_prefix + query.term});
        query.callback(data)
      createSearchChoice: (term, data) -> return data
  else
    ele.select2
      minimumResultsForSearch: 99
      data: options
      placeholder: placeholder

  if selected
    ele.data('select2').data(selected)


# -------------------------------------------------------------------
# Our basic modal, with just message and an OK button to dismiss it
# -------------------------------------------------------------------
class @Modal
  constructor: (@title, @message) ->
    modal = @
    @autoDismiss = true
    @ele = $('#modal-template').clone()
    @ele.data('object', @)
    @ele.attr('id', 'active-modal')
    @keyboard = true
    modalClose = @ele.find('.close')
    modalClose.on('click', -> modal.dismiss())

  setIcon: (@icon) ->
    @ele.find('.icon').addClass('glyph').addClass(@icon)

  setPrimaryButton: (buttonName=gettext('Ok')) ->
    primary = @ele.find('.primary')
    primary.text(buttonName)

  setTertiaryButton: (buttonName='Options', handler) ->
    tertiary = @ele.find('.tertiary')
    tertiary.text(buttonName)
    tertiary.on 'click', handler
    tertiary.show()

  show: ->
    modal = @

    @ele.on 'hidden', ->
      if modal.listeners and modal.listeners.onDismiss
        modal.listeners.onDismiss(modal)

    @ele.find('#modal-title').html(@title)
    if @message
      @ele.find('#modal-message').html(@message)
    else
      @ele.find('#modal-message').hide()
    @ele.modal
      show: true
      backdrop: 'static'
      keyboard: @keyboard


  addListener: (event, listener) ->
    @listeners[event] = listener

  setListeners: (@listeners, @autoDismiss=true) ->
    modal = @
    primary = @ele.find('.primary')

    if @listeners.onPrimary
      primary.off('click').on 'click', ->
        if modal.listeners.onBeforePrimary
          if modal.listeners.onBeforePrimary(modal)
            return
        modal.listeners.onPrimary(modal)

        if modal.autoDismiss
          modal.dismiss()

    else
      if modal.autoDismiss
        primary.on 'click', -> modal.dismiss()

  setMessage: (@message) ->

  dismiss: ->
    @ele.modal('hide')
    @ele.remove()

  addClass: (className) ->
    @ele.addClass(className)

  focusFirstInput: ->
    @ele.find("input,textarea").filter(':first').focus()

# -------------------------------------------------------------------
# A button that can be populated with a JQuery element and has
# a primary and secondary button
# -------------------------------------------------------------------
class @ConfirmationModal extends @Modal
  constructor: (title, message) ->
    super(title, message)
    modal = @
    secondary = @ele.find('.secondary')
    secondary.on('click', -> modal.dismiss())
    secondary.show()

  hideSecondaryButton: ->
    @ele.find('.secondary').hide()

  setForm: (form) ->
    @ele.find('.modal-body .form').append(form)

  getForm: ->
    return @ele.find('.modal-body .form').children(0)

  show: ->
    super()
    @focusFirstInput()

  setListeners: (listeners, autoDismiss=true) ->
    super(listeners, autoDismiss)
    modal = @
    if modal.listeners.onSecondary
      secondary = @ele.find('.secondary')
      secondary.on 'click', ->
        modal.listeners.onSecondary(modal)

# -------------------------------------------------------------------
# A modal populated with a PJAX element
# -------------------------------------------------------------------
class @Modax extends @ConfirmationModal
    constructor: (title, @url) ->
      super(title, null)
      modal = @

      @ele.find('.primary').on('click', ->
        modal.submit()
      )

    setRedirectOnSuccess: (@redirectOnSuccess) ->

    setListeners: (listeners, autoDismiss=false) ->
      super(listeners, autoDismiss)

    show: ->
      super()
      @ele.find('.loader').show()

      modal = @
      fetchPJAXContent(@url, "#active-modal .fetched-content",
        onSuccess: ->
          modal.ele.find('.loader').hide()
          modal.submitText = modal.ele.find(".form-actions input[type='submit']").val()
          modal.ele.find(".primary").text(modal.submitText)
          modal.focusFirstInput()
          if modal.listeners and modal.listeners.onFormLoaded
            modal.listeners.onFormLoaded()

          modal.wireEnter()
          prepareOmnibox()
      )

    # trap ENTER on the form, use our modal submit
    wireEnter: ->
      modal = @
      modal.ele.find("form").on('keydown', (e) ->
        if e.keyCode == ENTER
          modal.submit()
          return false
        )
 
    submit: ->
      modal = @
      modal.ele.find('.primary').text(gettext("Processing..")).addClass("disabled")
      postData = modal.ele.find('form').serialize();
      fetchPJAXContent(@url, '#active-modal .fetched-content',
        postData: postData
        shouldIgnore: (data) ->
          ignore = /success-script/i.test(data)
          return ignore

        onIgnore: (xhr) ->
          if not modal.redirectOnSuccess
            modal.ele.find(".primary").removeClass("disabled").text(modal.submitText)

          if modal.listeners
            if modal.listeners.onCompleted
              modal.listeners.onCompleted(xhr)

            # this is actually the success case for Modax modals
            if modal.listeners.onSuccess
              modal.listeners.onSuccess(xhr)

          if modal.redirectOnSuccess
            modal.ele.find('.fetched-content').hide()
            modal.ele.find('.loader').show()

            redirect = xhr.getResponseHeader("Temba-Success")
            if redirect
              document.location.href = redirect
            else
              modal.dismiss()
          else
            modal.dismiss()

        onSuccess: ->
          modal.ele.find(".primary").removeClass("disabled").text(modal.submitText)
          if modal.listeners and modal.listeners.onCompleted
              modal.listeners.onCompleted()
          else
            modal.wireEnter()
            modal.focusFirstInput()
      )

$ ->
  $('.uv-send-message').click ->
    UserVoice.push(['show', {}]);
