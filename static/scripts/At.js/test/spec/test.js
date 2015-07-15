(function () {
  'use strict';

  describe('matcher tests', function () {
    it('should match "" after flag', function () {
      var matched = matcher("@", "some texts before @", "@");
      expect(matched).toBe("");
    });

    it('should not match escaped texts', function () {
      var matched = matcher("@", "some texts before @@contact", "@");
      expect(matched).toBe(null);
    });

    it('should match variable after flag', function () {
      var matched = matcher("@", "some texts before @contact", "@");
      expect(matched).toBe("contact");
    });

    it('should match variables with dot', function () {
      var matched = matcher("@", "some texts before @contact.born", "@");
      expect(matched).toBe("contact.born");
    });

    it('should match variables with dot as big as possible', function () {
      var matched = matcher("@", "some texts before @contact.born.where.location", "@");
      expect(matched).toBe("contact.born.where.location");
    });

    it('should not match space if we have a space at the end', function () {
      var matched = matcher("@", "some texts before @contact ", "@");
      expect(matched).toBe(null);
    });

    it('should not match space if if last word does not have flag', function () {
      var matched = matcher("@", "some texts before @contact contact", "@");
      expect(matched).toBe(null);
    });

    it('should match functions', function () {
      var matched = matcher("@", "some texts before @(SUM", "@");
      expect(matched).toBe("(SUM");
    });

    it('should not match escaped functions', function () {
      var matched = matcher("@", "some texts before @@(SUM", "@");
      expect(matched).toBe(null);
    });

    it('should match all the function', function () {
      var matched = matcher("@", "some texts before @(SUM()", "@");
      expect(matched).toBe("(SUM()");
    });

    it('should match the function as long as possible', function () {
      var matched = matcher("@", "some texts before @(SUM(contact.age, step.value", "@");
      expect(matched).toBe("(SUM(contact.age, step.value");
    });

    it('should match the function as long as possible', function () {
      var matched = matcher("@", "some texts before @(SUM(contact.age, step.value))))", "@");
      expect(matched).toBe("(SUM(contact.age, step.value))))");
    });

    it('should not match if space after last )', function () {
      var matched = matcher("@", "some texts before @(SUM(contact.age, step.value)))) ", "@");
      expect(matched).toBe(null);
    });








  });

  describe('Find context query ', function () {
    describe('simple query', function () {
      it('simple query', function () {
        var query = find_context_query('contact');
        expect(query).toBe('contact');
      });

      it('simple query', function () {
        var query = find_context_query('(SUM');
        expect(query).toBe('SUM');
      });

      it('simple query', function () {
        var query = find_context_query('(SUM()');
        expect(query).toBe('SUM');
      });

      it('simple query', function () {
        var query = find_context_query('(SUM(contact');
        expect(query).toBe('contact');
      });

      it('simple query', function () {
        var query = find_context_query('(SUM(contact.age');
        expect(query).toBe('contact.age');
      });

      it('simple query', function () {
        var query = find_context_query('(SUM(contact.age, step.category');
        expect(query).toBe('step.category');
      });

      it('simple query', function () {
        var query = find_context_query('(SUM(contact.age, step.category)');
        expect(query).toBe('SUM');
      });

    });
  });

})();
